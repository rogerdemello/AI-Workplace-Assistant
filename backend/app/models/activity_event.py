from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, JSON
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    event_source = Column(String(40), nullable=False, default="web", index=True)
    activity_state = Column(String(24), nullable=True)
    event_at = Column(DateTime, default=utcnow_naive, index=True)
    event_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
