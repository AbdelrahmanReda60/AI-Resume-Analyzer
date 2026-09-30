from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    resume_id: Optional[int] = None
    job_id: Optional[int] = None

class ActionableRecommendation(BaseModel):
    category: str
    title: str
    provider: Optional[str] = "Online Course"
    reason: str

class ChatResponse(BaseModel):
    session_id: str
    user_message: str
    reply: str
    actionable_recommendations: List[ActionableRecommendation] = []
    suggested_followups: List[str] = []

class ChatMessageResponse(BaseModel):
    id: int
    sender: str
    message: str
    timestamp: datetime
