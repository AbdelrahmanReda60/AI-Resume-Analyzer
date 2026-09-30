import json
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.resume import Resume
from app.models.analysis import Analysis
from app.models.job import Job

router = APIRouter(prefix="/resumes", tags=["Improvements"])

# Skills considered critical when a posting asks for them often enough.
CRITICAL = {"docker", "kubernetes", "fastapi", "aws"}

# Official, stable documentation URLs for the skills the KB and jobs care about.
SKILL_RESOURCES = {
    "kubernetes": ("Kubernetes official tutorials", "Documentation", "https://kubernetes.io/docs/tutorials/"),
    "docker": ("Docker get-started guide", "Documentation", "https://docs.docker.com/get-started/"),
    "aws": ("AWS training and certification", "Training", "https://aws.amazon.com/training/"),
    "fastapi": ("FastAPI official tutorial", "Documentation", "https://fastapi.tiangolo.com/tutorial/"),
    "postgresql": ("PostgreSQL official tutorial", "Documentation", "https://www.postgresql.org/docs/current/tutorial.html"),
    "sql": ("SQLBolt interactive lessons", "Course", "https://sqlbolt.com/"),
    "pytorch": ("PyTorch official tutorials", "Documentation", "https://pytorch.org/tutorials/"),
    "redis": ("Redis learn center", "Documentation", "https://redis.io/docs/latest/learn/"),
    "terraform": ("Terraform getting started", "Documentation", "https://developer.hashicorp.com/terraform/tutorials"),
    "machine learning": ("Google Machine Learning Crash Course", "Course", "https://developers.google.com/machine-learning/crash-course"),
    "javascript": ("MDN JavaScript guide", "Documentation", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide"),
    "git": ("Pro Git book", "Book", "https://git-scm.com/book/en/v2"),
    "linux": ("Linux journey", "Course", "https://linuxjourney.com/"),
    "security": ("OWASP Top Ten", "Documentation", "https://owasp.org/www-project-top-ten/"),
    "rest apis": ("MDN HTTP overview", "Documentation", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview"),
}

SKILL_CERTIFICATIONS = {
    "aws": {
        "title": "AWS Certified Developer – Associate",
        "provider": "Amazon Web Services",
        "link": "https://aws.amazon.com/certification/certified-developer-associate/",
    },
    "kubernetes": {
        "title": "Certified Kubernetes Application Developer (CKAD)",
        "provider": "The Linux Foundation",
        "link": "https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/",
    },
    "docker": {
        "title": "Docker Certified Associate",
        "provider": "Docker, Inc.",
        "link": "https://www.docker.com/certification/",
    },
    "postgresql": {
        "title": "PostgreSQL 15 Associate Certification",
        "provider": "EnterpriseDB",
        "link": "https://www.enterprisedb.com/training/postgres",
    },
    "pytorch": {
        "title": "Deep Learning with PyTorch",
        "provider": "Udacity",
        "link": "https://www.udacity.com/course/deep-learning-pytorch--ud188",
    },
    "terraform": {
        "title": "HashiCorp Certified: Terraform Associate",
        "provider": "HashiCorp",
        "link": "https://developer.hashicorp.com/certifications/terraform-associate",
    },
}

METRIC_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|percent|ms|s\b|x\b)|\$\s?\d|\d[\d,]*\s*(?:users|requests|transactions|clients|projects)")


def _load_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return value if isinstance(value, list) else []


def _job_skill_demand(db: Session) -> dict[str, dict]:
    """How many active postings require each skill -> {count, display name}."""
    demand: dict[str, dict] = {}
    for job in db.query(Job).filter(Job.is_active.is_(True)).all():
        for skill in _load_json_list(job.required_skills):
            display = str(skill).strip()
            key = display.lower()
            if not key:
                continue
            row = demand.setdefault(key, {"count": 0, "display": display})
            row["count"] += 1
    return demand


def _has_metrics(experience_text: str) -> bool:
    return bool(METRIC_RE.search(experience_text or ""))


@router.get("/{resume_id}/improvements")
def get_resume_improvements(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == current_user.id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID {resume_id} not found."
        )

    analysis = db.query(Analysis).filter(Analysis.resume_id == resume_id).first()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume must be analyzed before retrieving improvement suggestions."
        )

    tech_skills = [str(s) for s in _load_json_list(analysis.technical_skills)]
    soft_skills = [str(s) for s in _load_json_list(analysis.soft_skills)]
    experience_text = " ".join(str(e) for e in _load_json_list(analysis.experience))
    education = _load_json_list(analysis.education)
    summary = (analysis.summary or "").strip()
    years = analysis.years_of_experience or 0
    tech_keys = {s.strip().lower() for s in tech_skills}

    # ---- Missing high-demand skills, ranked by how many postings need them ----
    demand = _job_skill_demand(db)
    missing_rows = []
    for skill_key, info in demand.items():
        if skill_key in tech_keys:
            continue
        count = info["count"]
        missing_rows.append({
            "skill": info["display"],
            "importance": "High" if (count >= 4 or skill_key in CRITICAL) else "Medium",
            "appears_in_job_matches": count,
        })
    missing_rows.sort(key=lambda r: (-r["appears_in_job_matches"], r["skill"]))
    missing_skills = missing_rows[:5]

    # ---- Strengths (all derived from the analysis) ----
    strengths = []
    if len(tech_skills) >= 5:
        strengths.append(f"Solid technical base spanning {len(tech_skills)} skills "
                         f"({', '.join(tech_skills[:4])}).")
    if years >= 3:
        strengths.append(f"{years} year(s) of documented experience supports mid/senior-level roles.")
    if soft_skills:
        strengths.append(f"Explicit soft-skill coverage: {', '.join(soft_skills[:4])}.")
    if _has_metrics(experience_text):
        strengths.append("Experience bullets contain quantified metrics (percentages, volumes, or dollar figures).")
    if education:
        strengths.append("Education section is present and matches common degree requirements.")
    if not strengths:
        strengths.append("Resume parsed cleanly with a readable skills section.")

    # ---- Weaknesses (all derived from the analysis) ----
    weaknesses = []
    if missing_skills:
        top = ", ".join(m["skill"] for m in missing_skills[:3])
        weaknesses.append(f"Missing high-demand skills found in job postings: {top}.")
    if not _has_metrics(experience_text):
        weaknesses.append("Experience bullets lack quantified outcomes — add percentages, volumes, or time saved.")
    if not soft_skills:
        weaknesses.append("No soft skills listed; recruiters frequently screen for communication and teamwork.")
    if not education:
        weaknesses.append("Education section is missing or could not be parsed.")
    if len(summary) < 60:
        weaknesses.append("Summary is too short — aim for 2–3 sentences stating focus, years, and stack.")
    if years and years < 3:
        weaknesses.append("Under 3 years of experience; emphasize projects and certifications to offset this.")
    if not weaknesses:
        weaknesses.append("No critical gaps detected — tailor the resume per application to stay competitive.")

    # ---- Recommendations ----
    certifications = []
    for row in missing_skills:
        cert = SKILL_CERTIFICATIONS.get(row["skill"].lower())
        if cert and cert not in certifications:
            certifications.append(dict(cert))
    if not certifications:
        certifications.append(dict(SKILL_CERTIFICATIONS["aws"]))

    resources = []
    for row in missing_skills:
        res = SKILL_RESOURCES.get(row["skill"].lower())
        if res and res[2] not in {r["url"] for r in resources}:
            resources.append({"skill": row["skill"], "resource_name": res[0], "type": res[1], "url": res[2]})
    for key in list(SKILL_RESOURCES)[:6]:
        if len(resources) >= 4:
            break
        if key in tech_keys:
            res = SKILL_RESOURCES[key]
            if res[2] not in {r["url"] for r in resources}:
                resources.append({"skill": key.title(), "resource_name": res[0], "type": res[1], "url": res[2]})
    if not resources:
        res = SKILL_RESOURCES["fastapi"]
        resources.append({"skill": "FastAPI", "resource_name": res[0], "type": res[1], "url": res[2]})

    # ---- Actionable bullet edits ----
    bullets = []
    if not _has_metrics(experience_text):
        bullets.append("Rewrite each experience bullet to start with an action verb and end with a metric "
                       "(e.g. \"Optimized SQL queries, cutting p95 latency by 45%\").")
    if missing_skills:
        bullets.append(f"Add a \"Technical Skills\" row that names {missing_skills[0]['skill']} explicitly — "
                       f"{missing_skills[0]['appears_in_job_matches']} of the seeded postings require it.")
    if len(summary) < 60 or not summary:
        bullets.append("Expand the professional summary to 2–3 sentences: years of experience, target role, "
                       "and 3 headline technologies.")
    if not education:
        bullets.append("Add an Education section (degree, institution, graduation year) — many filters require it.")
    if years and years < 3:
        bullets.append("Compensate for limited tenure with a Projects section showing deployed, linkable work.")
    else:
        bullets.append("Add a \"Key Projects\" section with a one-line goal, your stack, and a GitHub/demo link.")
    if not soft_skills:
        bullets.append("Add 3–4 soft skills (Communication, Leadership, Problem Solving) that mirror the job ads.")
    bullets = bullets[:5]

    # ---- Readiness score: weighted, deterministic, 0–100 ----
    score = 30
    score += min(30, len(tech_skills) * 3)                       # up to 30 — skill breadth
    score += 10 if _has_metrics(experience_text) else 0          # 10  — quantified impact
    score += 10 if education else 0                              # 10  — education
    score += 10 if soft_skills else 0                            # 10  — soft skills
    score += 10 if len(summary) >= 60 else 0                     # 10  — summary quality
    if demand:
        total_demand = sum(info["count"] for info in demand.values())
        covered = sum(info["count"] for k, info in demand.items() if k in tech_keys)
        score += round(10 * covered / max(1, total_demand))  # up to 10 — market coverage
    score = max(0, min(100, score))

    return {
        "resume_id": resume_id,
        "overall_score": score,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "missing_critical_skills": missing_skills,
        "recommended_certifications": certifications,
        "learning_resources": resources,
        "actionable_bullet_improvements": bullets,
    }
