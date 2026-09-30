from pydantic import BaseModel
from typing import List, Optional
from app.schemas.job import JobResponse

class RecommendationItem(BaseModel):
    job: JobResponse
    match_score: int
    match_grade: str
    matched_technical_skills: List[str] = []
    missing_technical_skills: List[str] = []
    matched_soft_skills: List[str] = []
    missing_soft_skills: List[str] = []
    experience_fit: Optional[str] = None
    education_fit: Optional[str] = None
    explanation: Optional[str] = None

class RecommendationListResponse(BaseModel):
    resume_id: int
    total_matched: int
    recommendations: List[RecommendationItem]
