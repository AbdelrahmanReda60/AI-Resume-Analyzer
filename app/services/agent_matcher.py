import json
import logging

from app.models.job import Job
from app.schemas.job import JobResponse
from app.schemas.recommendation import RecommendationItem
from app.schemas.resume import AnalysisResult
from app.services import llm_client
from app.services.vector_store import calculate_tf_idf_similarity

logger = logging.getLogger("ai_resume_analyzer.matcher")

# 5-factor weights (docs/PLAN.md section 4.1)
WEIGHTS = {"tech": 0.40, "soft": 0.10, "exp": 0.25, "edu": 0.10, "sem": 0.15}

DEGREE_RANKS = [
    (5, ("doctorate", "ph.d", "phd", "doctoral")),
    (4, ("master", "mba", "m.s", "m.a", "mtech", "m.eng")),
    (3, ("bachelor", "b.s", "b.a", "b.tech", "b.eng", "undergraduate", "licence")),
    (2, ("associate", "foundation year", "higher diploma")),
    (1, ("high school", "secondary", "diploma", "gcse", "baccalaureate")),
]


def degree_rank(text: str | None) -> int:
    """Map a free-text degree to a comparable rank (0 = unknown/none)."""
    if not text:
        return 0
    lowered = text.lower()
    if any(no_degree in lowered for no_degree in ("no degree", "none", "not specified")):
        return 0
    for rank, needles in DEGREE_RANKS:
        if any(needle in lowered for needle in needles):
            return rank
    return 0


def candidate_degree_rank(analysis: AnalysisResult) -> int:
    """Highest degree rank found anywhere in the candidate's education history."""
    best = 0
    for entry in analysis.education or []:
        degree = getattr(entry, "degree", "") or ""
        institution = getattr(entry, "institution", "") or ""
        best = max(best, degree_rank(degree), degree_rank(institution))
    return best


def calculate_job_match(analysis: AnalysisResult, job: Job) -> RecommendationItem:
    """
    Calculates the deterministic 5-factor weighted score:
    - Tech Skills Coverage (40%)
    - Soft Skills Coverage (10%)
    - Experience Duration Fit (25%)
    - Education Fit (10%)
    - Semantic Similarity (15%)
    """
    cand_tech = {s.lower().strip() for s in (analysis.technical_skills or [])}
    cand_soft = {s.lower().strip() for s in (analysis.soft_skills or [])}

    try:
        job_req_tech = {s.lower().strip() for s in json.loads(job.required_skills)}
    except (TypeError, json.JSONDecodeError):
        job_req_tech = {s.lower().strip() for s in (job.required_skills or "").split(",") if s.strip()}

    try:
        job_soft = {s.lower().strip() for s in json.loads(job.soft_skills)} if job.soft_skills else set()
    except (TypeError, json.JSONDecodeError):
        job_soft = set()

    # 1. Tech Skills Score (40%)
    if job_req_tech:
        matched_tech_set = cand_tech.intersection(job_req_tech)
        missing_tech_set = job_req_tech - cand_tech
        s_tech = (len(matched_tech_set) / len(job_req_tech)) * 100
    else:
        matched_tech_set = set()
        missing_tech_set = set()
        s_tech = 100.0

    # 2. Soft Skills Score (10%)
    if job_soft:
        matched_soft_set = cand_soft.intersection(job_soft)
        missing_soft_set = job_soft - cand_soft
        s_soft = (len(matched_soft_set) / len(job_soft)) * 100
    else:
        matched_soft_set = cand_soft
        missing_soft_set = set()
        s_soft = 100.0

    # 3. Experience Score (25%)
    cand_years = analysis.years_of_experience or 0
    req_years = job.min_years_experience or 0
    if req_years == 0 or cand_years >= req_years:
        s_exp = 100.0
        exp_fit_notes = f"Candidate has {cand_years} yrs exp vs {req_years} yrs required (Fully meets)."
    else:
        s_exp = (cand_years / req_years) * 100.0
        exp_fit_notes = f"Candidate has {cand_years} yrs exp vs {req_years} yrs required (Partial fit)."

    # 4. Education Score (10%) - real degree-tier comparison
    cand_rank = candidate_degree_rank(analysis)
    req_rank = degree_rank(job.required_degree)
    if req_rank == 0 or cand_rank >= req_rank:
        s_edu = 100.0
        edu_fit_notes = "Degree qualification meets or exceeds the job requirement."
    elif cand_rank == 0:
        s_edu = 30.0
        edu_fit_notes = f"No qualifying degree found; job asks for a {job.required_degree} level."
    else:
        s_edu = 60.0
        edu_fit_notes = f"Candidate degree is one tier below the required {job.required_degree} level (partial credit)."

    # 5. Semantic Similarity Score (15%)
    cand_text = f"{analysis.summary} {' '.join(analysis.technical_skills)}"
    s_sem = calculate_tf_idf_similarity(job.description, cand_text) * 100.0

    # Composite Weighted Score
    final_score = (
        WEIGHTS["tech"] * s_tech
        + WEIGHTS["soft"] * s_soft
        + WEIGHTS["exp"] * s_exp
        + WEIGHTS["edu"] * s_edu
        + WEIGHTS["sem"] * s_sem
    )
    final_score = int(round(min(100.0, max(0.0, final_score))))

    # Match Grade
    if final_score >= 85:
        match_grade = "Exceptional Match"
    elif final_score >= 70:
        match_grade = "High Match"
    elif final_score >= 45:
        match_grade = "Moderate Match"
    else:
        match_grade = "Low Match"

    # Matched/Missing lists (Capitalized)
    matched_tech = [s.title() for s in matched_tech_set]
    missing_tech = [s.title() for s in missing_tech_set]
    matched_soft = [s.title() for s in matched_soft_set]
    missing_soft = [s.title() for s in missing_soft_set]

    # Deterministic explanation (used as-is, and as the LLM fallback)
    explanation = (
        f"Candidate scored {final_score}% for {job.title} at {job.company}. "
        f"Matched {len(matched_tech)} of {len(job_req_tech)} required technical skills. "
        + (
            f"Acquiring skills in {', '.join(missing_tech[:2])} will strengthen qualifications."
            if missing_tech
            else "Meets all key skill criteria."
        )
    )

    job_resp = JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        job_type=job.job_type,
        experience_level=job.experience_level,
        min_years_experience=job.min_years_experience,
        required_degree=job.required_degree,
        description=job.description,
        required_skills=list(job_req_tech),
        soft_skills=list(job_soft),
        salary_range=job.salary_range,
        is_active=job.is_active,
        created_at=job.created_at
    )

    return RecommendationItem(
        job=job_resp,
        match_score=final_score,
        match_grade=match_grade,
        matched_technical_skills=matched_tech,
        missing_technical_skills=missing_tech,
        matched_soft_skills=matched_soft,
        missing_soft_skills=missing_soft,
        experience_fit=exp_fit_notes,
        education_fit=edu_fit_notes,
        explanation=explanation
    )


def enrich_explanations(analysis: AnalysisResult, items: list[RecommendationItem]) -> None:
    """
    Ask the LLM for natural-language explanations of the top matches in a SINGLE
    batched call, so scoring stays fast. Silently keeps the deterministic
    explanation when the LLM is unavailable or fails.
    """
    if not items or not llm_client.llm_available():
        return

    lines = []
    for index, item in enumerate(items):
        lines.append(
            f"{index}|{item.job.title} at {item.job.company}|score={item.match_score}|"
            f"matched={', '.join(item.matched_technical_skills)}|"
            f"missing={', '.join(item.missing_technical_skills)}|"
            f"{item.experience_fit}|{item.education_fit}"
        )

    prompt = (
        "You are an AI Job Matching Specialist. For each numbered job match below, "
        "write a fair 1-2 sentence explanation of why this candidate fits (or does not fit) "
        "the role. Mention the strongest matched skills and the most important missing skill. "
        "Be objective and specific. "
        f"Candidate: {(analysis.full_name or 'Candidate')} with "
        f"{analysis.years_of_experience or 0} years of experience. "
        f"Skills: {', '.join(analysis.technical_skills[:12])}. "
        f"Summary: {(analysis.summary or '')[:400]}\n\n"
        "Matches:\n" + "\n".join(lines) + "\n\n"
        'Return ONLY valid JSON: {"explanations": {"<index>": "<explanation>", ...}} '
        "covering every index listed."
    )

    try:
        parsed = llm_client.generate_json(prompt, timeout=15)
        explanations = parsed.get("explanations") or {}
        if isinstance(explanations, list):
            explanations = {str(i): text for i, text in enumerate(explanations)}
        for index, item in enumerate(items):
            text = explanations.get(str(index))
            if isinstance(text, str) and text.strip():
                item.explanation = text.strip()
    except Exception as exc:  # noqa: BLE001 - explanations are best-effort
        logger.warning("Match explanation LLM call skipped: %s", type(exc).__name__)
