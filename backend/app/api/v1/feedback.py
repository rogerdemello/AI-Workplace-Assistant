from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID, uuid4
import hashlib
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...database import get_db
from ...models.chat_feedback import ChatFeedback
from ...models.user import User

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    category: str
    message: str


class FeedbackResponse(BaseModel):
    token: str
    status: str


class ChatCSATCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    conversation_id: Optional[UUID] = None
    comment: Optional[str] = None
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    source: str = "chat"


class ChatCSATResponse(BaseModel):
    id: UUID
    rating: int
    created_at: datetime
    status: str


@router.post("/anonymous", response_model=FeedbackResponse)
def submit_anonymous_feedback(feedback: FeedbackCreate):
    """
    Submit anonymous feedback without authentication.
    Returns a token that can be used to track the feedback status (shown only once).
    """
    # Validate category
    valid_categories = ['culture', 'management', 'benefits', 'workload', 'other']
    if feedback.category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )
    
    # Validate message
    if not feedback.message or not feedback.message.strip():
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty"
        )
    
    if len(feedback.message) > 5000:
        raise HTTPException(
            status_code=400,
            detail="Message cannot exceed 5000 characters"
        )
    
    # Generate anonymous token
    token = str(uuid4())
    # Hash token for storage (only show once)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    # In production, you would save to database here:
    # feedback_record = Feedback(
    #     token_hash=token_hash,
    #     category=feedback.category,
    #     message=feedback.message
    # )
    # db.add(feedback_record)
    # db.commit()
    
    return FeedbackResponse(token=token, status="submitted")


@router.get("/categories")
def get_feedback_categories():
    """Get list of available feedback categories."""
    return [
        {"value": "culture", "label": "Work Culture"},
        {"value": "management", "label": "Management"},
        {"value": "benefits", "label": "Benefits"},
        {"value": "workload", "label": "Workload"},
        {"value": "other", "label": "Other"}
    ]


@router.post("/csat", response_model=ChatCSATResponse, status_code=status.HTTP_201_CREATED)
def submit_chat_csat(
    payload: ChatCSATCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Capture in-chat CSAT ratings for quality monitoring."""
    comment = (payload.comment or "").strip() or None
    if comment and len(comment) > 1200:
        raise HTTPException(status_code=400, detail="Comment cannot exceed 1200 characters")

    row = ChatFeedback(
        user_id=current_user.id,
        conversation_id=payload.conversation_id,
        rating=payload.rating,
        comment=comment,
        intent=(payload.intent or None),
        sentiment=(payload.sentiment or None),
        source=(payload.source or "chat"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return ChatCSATResponse(
        id=row.id,
        rating=row.rating,
        created_at=row.created_at,
        status="submitted",
    )
