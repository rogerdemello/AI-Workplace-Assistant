from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Enum as SQLEnum, Text, Integer
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from ..database import Base
from ..core.time import utcnow_naive


class MoodEmoji(str, enum.Enum):
    happy = "🙂"
    neutral = "😐"
    sad = "😟"
    upset = "😔"


class MoodEntry(Base):
    __tablename__ = "mood_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    mood_emoji = Column(SQLEnum(MoodEmoji), nullable=False, index=True)
    mood_score = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)

    user = relationship("User", foreign_keys=[user_id])