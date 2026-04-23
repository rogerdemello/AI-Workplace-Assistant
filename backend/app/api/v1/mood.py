from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ...database import get_db
from ...schemas.mood import MoodCreate, MoodResponse, MoodTrendResponse
from ...auth import get_current_user
from ...models.user import User
from ...services.mood_service import log_mood, get_mood_history, get_mood_trend

router = APIRouter(prefix="/mood", tags=["mood"])


@router.post("", response_model=MoodResponse, status_code=status.HTTP_201_CREATED)
def create_mood(
    mood_data: MoodCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = log_mood(
        db=db,
        user_id=current_user.id,
        mood_emoji=mood_data.mood_emoji,
        mood_score=mood_data.mood_score,
        note=mood_data.note
    )
    return record


@router.get("/{user_id}", response_model=List[MoodResponse])
def get_mood(
    user_id: UUID,
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Users can only view their own mood history unless they're manager/hr/admin
    if user_id != current_user.id and current_user.role not in ["hr", "admin", "manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this user's mood history")
    
    records = get_mood_history(db=db, user_id=user_id, days=days)
    return records


@router.get("/{user_id}/trend", response_model=MoodTrendResponse)
def get_trend(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Users can only view their own mood trend unless they're manager/hr/admin
    if user_id != current_user.id and current_user.role not in ["hr", "admin", "manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this user's mood trend")
    
    trend = get_mood_trend(db=db, user_id=user_id)
    return trend