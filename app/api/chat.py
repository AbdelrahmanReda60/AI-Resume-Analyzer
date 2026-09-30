import json
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.resume import Resume
from app.models.analysis import Analysis
from app.models.chat import ChatMessage
from app.schemas.chat import ChatRequest, ChatResponse, ChatMessageResponse
from app.schemas.resume import AnalysisResult
from app.services.agent_advisor import generate_career_advice

router = APIRouter(prefix="/chat", tags=["Career Advisor Chat"])


def _session_key(user_id: int, resume_id: int | None, job_id: int | None) -> str:
    """Stable session id so a user's conversation is continuous across turns."""
    return f"u{user_id}-r{resume_id or 0}-j{job_id or 0}"

@router.post("", response_model=ChatResponse)
def send_chat_message(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume_analysis = None
    if payload.resume_id:
        # Check ownership: a user may only chat in the context of their own resume
        resume = db.query(Resume).filter(Resume.id == payload.resume_id, Resume.user_id == current_user.id).first()
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume with ID {payload.resume_id} not found."
            )
        an_rec = db.query(Analysis).filter(Analysis.resume_id == payload.resume_id).first()
        if an_rec:
            resume_analysis = AnalysisResult(
                full_name=an_rec.full_name,
                email=an_rec.email,
                phone=an_rec.phone,
                location=an_rec.location,
                summary=an_rec.summary,
                technical_skills=json.loads(an_rec.technical_skills) if an_rec.technical_skills else [],
                soft_skills=json.loads(an_rec.soft_skills) if an_rec.soft_skills else [],
                education=json.loads(an_rec.education) if an_rec.education else [],
                experience=json.loads(an_rec.experience) if an_rec.experience else [],
                years_of_experience=an_rec.years_of_experience or 0,
                domain_strengths=json.loads(an_rec.domain_strengths) if an_rec.domain_strengths else []
            )

    # One stable session per user (per resume context) so the agent has real memory
    session_id = _session_key(current_user.id, payload.resume_id, payload.job_id)

    # Prior turns are loaded BEFORE the new message so the agent can see the conversation
    history = db.query(ChatMessage).filter(
        ChatMessage.user_id == current_user.id,
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).limit(20).all()
    history_context = [{"sender": m.sender, "message": m.message} for m in history]

    # Save user message to DB
    user_msg = ChatMessage(
        user_id=current_user.id,
        resume_id=payload.resume_id,
        session_id=session_id,
        sender="user",
        message=payload.message
    )
    db.add(user_msg)
    db.commit()

    # Generate Career Advisor response
    bot_response = generate_career_advice(
        db,
        payload.message,
        resume_analysis=resume_analysis,
        session_id=session_id,
        history=history_context,
        job_context=payload.job_id,
    )

    # Save assistant response to DB
    bot_msg = ChatMessage(
        user_id=current_user.id,
        resume_id=payload.resume_id,
        session_id=session_id,
        sender="assistant",
        message=bot_response.reply,
        metadata_json=json.dumps([r.model_dump() for r in bot_response.actionable_recommendations])
    )
    db.add(bot_msg)
    db.commit()

    return bot_response

@router.get("/history", response_model=list[ChatMessageResponse])
def get_chat_history(
    limit: int = Query(50, ge=1, le=100),
    resume_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Take the MOST RECENT `limit` messages, then present them oldest-first
    query = db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id)
    if resume_id is not None:
        query = query.filter(ChatMessage.resume_id == resume_id)

    recent_ids = [row[0] for row in query.order_by(
        ChatMessage.created_at.desc(), ChatMessage.id.desc()
    ).limit(limit).with_entities(ChatMessage.id).all()]

    if not recent_ids:
        return []

    messages = db.query(ChatMessage).filter(ChatMessage.id.in_(recent_ids)) \
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).all()

    return [
        ChatMessageResponse(
            id=m.id,
            sender=m.sender,
            message=m.message,
            timestamp=m.created_at
        ) for m in messages
    ]

@router.delete("/history")
def clear_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).delete()
    db.commit()
    return {"detail": "Chat history cleared successfully."}
