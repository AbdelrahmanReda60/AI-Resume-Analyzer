import json
import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.models.job import Job
from app.schemas.chat import ActionableRecommendation, ChatResponse
from app.schemas.resume import AnalysisResult
from app.services import llm_client
from app.services.llm_client import LLMError
from app.services.rag_service import retrieve_rag_context

logger = logging.getLogger("ai_resume_analyzer.advisor")

DEFAULT_FOLLOWUPS = [
    "What certifications should I prepare for?",
    "How can I tailor my resume bullet points for cloud roles?",
    "What projects will best demonstrate my technical skills?",
]


def _fallback_recommendations() -> list[ActionableRecommendation]:
    return [ActionableRecommendation(
        category="Course",
        title="FastAPI & Cloud Microservices Architecture",
        provider="Coursera / Udemy",
        reason="Builds essential backend framework skills identified in market trends.",
    )]


def _sources_block(cited_sources: list) -> str:
    if not cited_sources:
        return ""
    labels = []
    for source in cited_sources[:4]:
        citation = source.get("citation") or source.get("title")
        if citation and citation not in labels:
            labels.append(citation)
    if not labels:
        return ""
    return "\n\nSources: " + ", ".join(labels)


def generate_career_advice(
    db: Session,
    user_message: str,
    resume_analysis: AnalysisResult | None = None,
    session_id: str | None = None,
    history: list[dict] | None = None,
    job_context: int | None = None,
) -> ChatResponse:
    """
    RAG-grounded Career Advisor Chat agent.
    1. Retrieves top-K context from the Knowledge Base BEFORE any generation.
    2. Builds an LLM prompt (or uses the rule-based fallback).
    3. Always cites the retrieved sources in the reply.
    """
    current_session = session_id or "session-default"

    # ---- 1. RAG retrieval happens before generation ----
    rag_context_str, cited_sources = retrieve_rag_context(db, user_message, top_k=4)

    # ---- Candidate / job context ----
    resume_summary = ""
    if resume_analysis:
        resume_summary = (
            f"Candidate Profile: {resume_analysis.full_name or 'Candidate'}, "
            f"{resume_analysis.years_of_experience or 0} years of experience. "
            f"Technical Skills: {', '.join(resume_analysis.technical_skills[:8])}. "
            f"Summary: {(resume_analysis.summary or '')[:400]}"
        )

    job_summary = ""
    if job_context:
        job = db.query(Job).filter(Job.id == job_context).first()
        if job:
            try:
                skills = json.loads(job.required_skills) if job.required_skills else []
            except (TypeError, json.JSONDecodeError):
                skills = []
            job_summary = (
                f"Target Job: {job.title} at {job.company} ({job.location}). "
                f"Required skills: {', '.join(skills)}. "
                f"Description: {(job.description or '')[:600]}"
            )

    history_block = ""
    if history:
        turns = history[-8:]
        history_block = "Conversation so far:\n" + "\n".join(
            f"{t.get('sender', 'user')}: {t.get('message', '')[:300]}" for t in turns
        ) + "\n\n"

    reply_text = ""
    actionable_recs: list[ActionableRecommendation] = []
    followups = list(DEFAULT_FOLLOWUPS)

    # ---- 2. LLM path (optional, always guarded) ----
    if llm_client.llm_available():
        prompt = f"""You are an expert AI Career Advisor and Mentor.
Answer the user's question using the provided RAG knowledge base context.
Quote the knowledge base source labels (e.g. [ROADMAP: ...]) when you rely on them.

{history_block}User Message: "{user_message}"

{resume_summary}
{job_summary}

Knowledge Base Context:
<<<
{rag_context_str}
>>>

Provide a helpful, encouraging, and clear answer.
Return ONLY valid JSON with keys:
  "reply" (String),
  "actionable_recommendations" (Array of objects: category, title, provider, reason),
  "suggested_followups" (Array of strings)
"""
        for attempt in range(2):
            try:
                parsed = llm_client.generate_json(prompt)
                candidate_reply = (parsed.get("reply") or "").strip()
                if not candidate_reply:
                    raise LLMError("LLM returned an empty reply")
                reply_text = candidate_reply
                for rec in parsed.get("actionable_recommendations") or []:
                    try:
                        actionable_recs.append(ActionableRecommendation(**rec))
                    except Exception:  # noqa: BLE001 - skip malformed entries
                        continue
                if parsed.get("suggested_followups"):
                    followups = [str(f) for f in parsed["suggested_followups"]][:4]
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Advisor LLM attempt %d failed: %s", attempt + 1, type(exc).__name__)
                reply_text = ""

    # ---- 3. Fallback + guaranteed source citation ----
    if not reply_text:
        logger.info("Advisor using RAG-grounded rule-based reply (no LLM response)")
        citation = cited_sources[0].get("title", "Knowledge Base") if cited_sources else "Knowledge Base"
        reply_text = (
            f"Based on our career knowledge base ({citation}), focus on mastering core "
            f"technical fundamentals and building hands-on portfolio projects. For your query "
            f"\"{user_message}\", structure your resume with quantified metrics and pursue "
            f"industry-standard certifications that match your target role."
        )
        if not actionable_recs:
            actionable_recs = _fallback_recommendations()

    # ---- Citations are appended on EVERY path ----
    reply_text = reply_text.rstrip() + _sources_block(cited_sources)

    return ChatResponse(
        session_id=current_session,
        user_message=user_message,
        reply=reply_text,
        actionable_recommendations=actionable_recs,
        suggested_followups=followups,
    )
