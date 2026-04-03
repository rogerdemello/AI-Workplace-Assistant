from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from uuid import UUID, uuid4
import hashlib

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    category: str
    message: str


class FeedbackResponse(BaseModel):
    token: str
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
