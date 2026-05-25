from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID, uuid4
import hashlib
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...database import get_db
from ...models.anonymous_feedback import AnonymousFeedback
from ...models.chat_feedback import ChatFeedback
from ...models.user import User

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    category: str
    message: str


class FeedbackResponse(BaseModel):
    token: str
    status: str


class FeedbackStatusResponse(BaseModel):
    status: str
    category: str
    created_at: datetime


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
def submit_anonymous_feedback(feedback: FeedbackCreate, db: Session = Depends(get_db)):
    """
    Submit anonymous feedback without authentication.
    Returns a token that can be used to track the feedback status (shown only once).

    Anonymity is structural: we persist only a one-way hash of the token and
    never any identity. The raw token is returned to the submitter once and is
    not recoverable afterwards.
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

    # Generate anonymous token; store only its hash so status can be checked
    # later without ever linking back to a person.
    token = str(uuid4())
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    record = AnonymousFeedback(
        token_hash=token_hash,
        category=feedback.category,
        message=feedback.message.strip(),
        status="submitted",
    )
    db.add(record)
    db.commit()

    return FeedbackResponse(token=token, status="submitted")


@router.get("/anonymous/status", response_model=FeedbackStatusResponse)
def get_anonymous_feedback_status(token: str, db: Session = Depends(get_db)):
    """Check the status of an anonymous submission using its one-time token."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    record = (
        db.query(AnonymousFeedback)
        .filter(AnonymousFeedback.token_hash == token_hash)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="No feedback found for that token.")
    return FeedbackStatusResponse(
        status=record.status,
        category=record.category,
        created_at=record.created_at,
    )


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
