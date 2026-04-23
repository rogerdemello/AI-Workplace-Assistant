from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum


class MoodEmoji(str, Enum):
    happy = "🙂"
    neutral = "😐"
    sad = "😟"
    upset = "😔"


class MoodCreate(BaseModel):
    mood_emoji: MoodEmoji
    mood_score: int
    note: Optional[str] = None


class MoodResponse(BaseModel):
    id: UUID
    user_id: UUID
    mood_emoji: MoodEmoji
    mood_score: int
    note: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MoodTrendResponse(BaseModel):
    average_score: Optional[float] = None
    trend: str
    total_entries: int
    oldest_entry: Optional[datetime] = None
    newest_entry: Optional[datetime] = None