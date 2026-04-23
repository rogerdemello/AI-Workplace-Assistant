import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, DateTime, UUID

from ..database import Base
from ..core.time import utcnow_naive


class HrAlert(Base):
    """Stored proactive / wellbeing alerts for HR review."""

    __tablename__ = "hr_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=True)
    severity = Column(String(32), nullable=False, default="medium")
    alert_type = Column(String(64), nullable=True)
    source = Column(String(64), nullable=False, default="proactive_wellbeing")
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    acknowledged = Column(Boolean, default=False, index=True)
