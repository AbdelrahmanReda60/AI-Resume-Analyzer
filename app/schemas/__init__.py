from app.schemas.auth import UserRegister, UserLogin, UserResponse, Token, TokenData
from app.schemas.resume import ResumeResponse, AnalysisResult, AnalysisResponse
from app.schemas.job import JobCreate, JobUpdate, JobResponse, JobListResponse
from app.schemas.recommendation import RecommendationItem, RecommendationListResponse
from app.schemas.chat import ChatRequest, ChatResponse, ChatMessageResponse
from app.schemas.kb import KBSearchItem, KBSearchResponse

__all__ = [
    "UserRegister", "UserLogin", "UserResponse", "Token", "TokenData",
    "ResumeResponse", "AnalysisResult", "AnalysisResponse",
    "JobCreate", "JobUpdate", "JobResponse", "JobListResponse",
    "RecommendationItem", "RecommendationListResponse",
    "ChatRequest", "ChatResponse", "ChatMessageResponse",
    "KBSearchItem", "KBSearchResponse"
]
