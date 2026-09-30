from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional

class ResumeResponse(BaseModel):
    id: int
    user_id: int
    title: str
    original_filename: str
    file_type: str
    file_size: int
    parsed_text_snippet: Optional[str] = None
    has_analysis: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ExperienceItem(BaseModel):
    company: Optional[str] = "Company"
    role: Optional[str] = "Role"
    duration: Optional[str] = "Duration"
    responsibilities: List[str] = []

class EducationItem(BaseModel):
    institution: Optional[str] = "Institution"
    degree: Optional[str] = "Degree"
    year: Optional[str] = "Year"

class AnalysisResult(BaseModel):
    full_name: Optional[str] = "Candidate"
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = "No summary provided."
    technical_skills: List[str] = []
    soft_skills: List[str] = []
    education: List[EducationItem] = []
    experience: List[ExperienceItem] = []
    years_of_experience: int = 0
    domain_strengths: List[str] = []

class AnalysisResponse(BaseModel):
    id: int
    resume_id: int
    status: str
    created_at: datetime
    result: AnalysisResult

    model_config = ConfigDict(from_attributes=True)
