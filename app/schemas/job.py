from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional

class JobCreate(BaseModel):
    title: str = Field(..., min_length=1)
    company: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    job_type: str = Field(default="Full-time")
    experience_level: str = Field(default="Mid")
    min_years_experience: int = Field(default=0, ge=0)
    required_degree: str = Field(default="Bachelor")
    description: str = Field(..., min_length=1)
    required_skills: List[str] = Field(..., min_length=1)
    soft_skills: Optional[List[str]] = []
    salary_range: Optional[str] = None

class JobUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    min_years_experience: Optional[int] = None
    required_degree: Optional[str] = None
    description: Optional[str] = None
    required_skills: Optional[List[str]] = None
    soft_skills: Optional[List[str]] = None
    salary_range: Optional[str] = None

class JobResponse(BaseModel):
    id: int
    title: str
    company: str
    location: str
    job_type: str
    experience_level: str
    min_years_experience: int
    required_degree: Optional[str] = "Bachelor"
    description: str
    required_skills: List[str]
    soft_skills: List[str] = []
    salary_range: Optional[str] = None
    is_active: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class JobListResponse(BaseModel):
    total: int
    jobs: List[JobResponse]
