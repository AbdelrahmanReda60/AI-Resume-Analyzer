import json
import os
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.resume import Resume
from app.models.analysis import Analysis
from app.schemas.resume import ResumeResponse, AnalysisResponse, AnalysisResult
from app.services.resume_parser import validate_and_parse_resume
from app.services.agent_analyzer import analyze_resume_text

router = APIRouter(prefix="/resumes", tags=["Resumes"])

@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
def upload_resume(
    file: UploadFile = File(...),
    title: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    saved_path, original_filename, file_type, file_size, extracted_text = validate_and_parse_resume(file)

    display_title = title.strip() if (title and title.strip()) else original_filename

    new_resume = Resume(
        user_id=current_user.id,
        title=display_title,
        file_path=saved_path,
        original_filename=original_filename,
        file_type=file_type,
        file_size=file_size,
        parsed_text=extracted_text
    )
    db.add(new_resume)
    db.commit()
    db.refresh(new_resume)

    return ResumeResponse(
        id=new_resume.id,
        user_id=new_resume.user_id,
        title=new_resume.title,
        original_filename=new_resume.original_filename,
        file_type=new_resume.file_type,
        file_size=new_resume.file_size,
        parsed_text_snippet=new_resume.parsed_text[:200] if new_resume.parsed_text else "",
        has_analysis=False,
        created_at=new_resume.created_at
    )

@router.get("", response_model=list[ResumeResponse])
def list_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resumes = db.query(Resume).filter(Resume.user_id == current_user.id).order_by(Resume.created_at.desc()).all()
    result = []
    for r in resumes:
        has_an = db.query(Analysis).filter(Analysis.resume_id == r.id).first() is not None
        result.append(ResumeResponse(
            id=r.id,
            user_id=r.user_id,
            title=r.title,
            original_filename=r.original_filename,
            file_type=r.file_type,
            file_size=r.file_size,
            parsed_text_snippet=r.parsed_text[:200] if r.parsed_text else "",
            has_analysis=has_an,
            created_at=r.created_at
        ))
    return result

@router.get("/{resume_id}", response_model=ResumeResponse)
def get_resume(
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

    has_an = db.query(Analysis).filter(Analysis.resume_id == resume.id).first() is not None
    return ResumeResponse(
        id=resume.id,
        user_id=resume.user_id,
        title=resume.title,
        original_filename=resume.original_filename,
        file_type=resume.file_type,
        file_size=resume.file_size,
        parsed_text_snippet=resume.parsed_text[:200] if resume.parsed_text else "",
        has_analysis=has_an,
        created_at=resume.created_at
    )

@router.delete("/{resume_id}")
def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == current_user.id).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found."
        )

    if os.path.exists(resume.file_path):
        try:
            os.remove(resume.file_path)
        except OSError:
            pass

    db.delete(resume)
    db.commit()
    return {"detail": "Resume and associated analyses deleted successfully."}

@router.post("/{resume_id}/analyze", response_model=AnalysisResponse)
def analyze_resume(
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

    # Run AI Resume Analyzer Agent
    analysis_data = analyze_resume_text(resume.parsed_text or "")

    # Save or update Analysis record
    existing = db.query(Analysis).filter(Analysis.resume_id == resume_id).first()
    if existing:
        analysis_record = existing
    else:
        analysis_record = Analysis(resume_id=resume_id)

    analysis_record.status = "completed"
    analysis_record.full_name = analysis_data.full_name
    analysis_record.email = analysis_data.email
    analysis_record.phone = analysis_data.phone
    analysis_record.location = analysis_data.location
    analysis_record.summary = analysis_data.summary
    analysis_record.technical_skills = json.dumps(analysis_data.technical_skills)
    analysis_record.soft_skills = json.dumps(analysis_data.soft_skills)
    analysis_record.education = json.dumps([e.model_dump() for e in analysis_data.education])
    analysis_record.experience = json.dumps([e.model_dump() for e in analysis_data.experience])
    analysis_record.years_of_experience = analysis_data.years_of_experience
    analysis_record.domain_strengths = json.dumps(analysis_data.domain_strengths)

    if not existing:
        db.add(analysis_record)
    db.commit()
    db.refresh(analysis_record)

    return AnalysisResponse(
        id=analysis_record.id,
        resume_id=resume_id,
        status="completed",
        created_at=analysis_record.created_at,
        result=analysis_data
    )

@router.get("/{resume_id}/analysis", response_model=AnalysisResponse)
def get_resume_analysis(
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis found for this resume. Please trigger analysis first."
        )

    result_data = AnalysisResult(
        full_name=analysis.full_name,
        email=analysis.email,
        phone=analysis.phone,
        location=analysis.location,
        summary=analysis.summary,
        technical_skills=json.loads(analysis.technical_skills) if analysis.technical_skills else [],
        soft_skills=json.loads(analysis.soft_skills) if analysis.soft_skills else [],
        education=json.loads(analysis.education) if analysis.education else [],
        experience=json.loads(analysis.experience) if analysis.experience else [],
        years_of_experience=analysis.years_of_experience or 0,
        domain_strengths=json.loads(analysis.domain_strengths) if analysis.domain_strengths else []
    )

    return AnalysisResponse(
        id=analysis.id,
        resume_id=resume_id,
        status=analysis.status,
        created_at=analysis.created_at,
        result=result_data
    )
