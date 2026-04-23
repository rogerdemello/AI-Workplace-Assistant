from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Integer
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class MeetingEvent(Base):
    __tablename__ = "meeting_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    meeting_title = Column(String(255), nullable=True)
    meeting_id = Column(String(100), nullable=True, index=True)
    duration_minutes = Column(Integer, nullable=True)
    meeting_at = Column(DateTime, default=utcnow_naive, index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)