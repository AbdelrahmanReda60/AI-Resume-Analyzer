import json
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.resume import Resume
from app.models.analysis import Analysis
from app.models.job import Job
from app.models.recommendation import Recommendation
from app.schemas.recommendation import RecommendationListResponse
from app.schemas.resume import AnalysisResult
from app.services.agent_matcher import calculate_job_match, enrich_explanations
from app.api.jobs import seed_jobs_if_empty

router = APIRouter(prefix="/resumes", tags=["Recommendations"])

@router.get("/{resume_id}/recommendations", response_model=RecommendationListResponse)
def get_recommendations(
    resume_id: int,
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(10, ge=1, le=50),
    explain: bool = Query(True, description="Set false to skip the LLM explanation pass (cheaper/faster)."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify ownership
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == current_user.id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID {resume_id} not found."
        )

    analysis_rec = db.query(Analysis).filter(Analysis.resume_id == resume_id).first()
    if not analysis_rec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume must be analyzed before requesting job recommendations."
        )

    # Reconstruct AnalysisResult
    analysis_data = AnalysisResult(
        full_name=analysis_rec.full_name,
        email=analysis_rec.email,
        phone=analysis_rec.phone,
        location=analysis_rec.location,
        summary=analysis_rec.summary,
        technical_skills=json.loads(analysis_rec.technical_skills) if analysis_rec.technical_skills else [],
        soft_skills=json.loads(analysis_rec.soft_skills) if analysis_rec.soft_skills else [],
        education=json.loads(analysis_rec.education) if analysis_rec.education else [],
        experience=json.loads(analysis_rec.experience) if analysis_rec.experience else [],
        years_of_experience=analysis_rec.years_of_experience or 0,
        domain_strengths=json.loads(analysis_rec.domain_strengths) if analysis_rec.domain_strengths else []
    )

    seed_jobs_if_empty(db)
    active_jobs = db.query(Job).filter(Job.is_active == True).all()

    # 1. Deterministic 5-factor scoring for every active job
    scored = [(job, calculate_job_match(analysis_data, job)) for job in active_jobs]

    # 2. Filter + sort high-to-low
    filtered = [(job, item) for job, item in scored if item.match_score >= min_score]
    filtered.sort(key=lambda pair: pair[1].match_score, reverse=True)
    visible = [item for _, item in filtered[:limit]]

    # 3. Single batched LLM call to polish the explanations of the visible matches
    if explain:
        enrich_explanations(analysis_data, visible)

    # 4. Persist every scored recommendation (upsert)
    for job, rec_item in scored:
        existing = db.query(Recommendation).filter(
            Recommendation.resume_id == resume_id,
            Recommendation.job_id == job.id
        ).first()

        if not existing:
            existing = Recommendation(
                resume_id=resume_id,
                job_id=job.id
            )
            db.add(existing)

        existing.match_score = rec_item.match_score
        existing.match_grade = rec_item.match_grade
        existing.matched_technical_skills = json.dumps(rec_item.matched_technical_skills)
        existing.missing_technical_skills = json.dumps(rec_item.missing_technical_skills)
        existing.matched_soft_skills = json.dumps(rec_item.matched_soft_skills)
        existing.missing_soft_skills = json.dumps(rec_item.missing_soft_skills)
        existing.experience_fit = rec_item.experience_fit
        existing.education_fit = rec_item.education_fit
        existing.explanation = rec_item.explanation

    db.commit()

    return RecommendationListResponse(
        resume_id=resume_id,
        total_matched=len(filtered),
        recommendations=visible
    )
