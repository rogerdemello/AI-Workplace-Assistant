from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, JSON, Float, Boolean
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class WellbeingSignal(Base):
    __tablename__ = "wellbeing_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True)
    source = Column(String(24), nullable=False, default="chat", index=True)
    sentiment_label = Column(String(16), nullable=False, index=True)
    sentiment_score = Column(Float, nullable=False)
    stress_indicator = Column(Float, nullable=False, default=0.0)
    burnout_indicator = Column(Float, nullable=False, default=0.0)
    triage_level = Column(String(16), nullable=False, default="none", index=True)
    requires_hr_followup = Column(Boolean, nullable=False, default=False, index=True)
    detected_keywords = Column(JSON, nullable=True)
    computed_at = Column(DateTime, default=utcnow_naive, index=True)
    signal_metadata = Column("metadata", JSON, nullable=True)
