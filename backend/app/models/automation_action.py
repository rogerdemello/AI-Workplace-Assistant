from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, JSON, Text
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class AutomationAction(Base):
    __tablename__ = "automation_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_name = Column(String(80), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    target_type = Column(String(40), nullable=False)
    action_type = Column(String(40), nullable=False)
    trigger_event_id = Column(UUID(as_uuid=True), ForeignKey("activity_events.id"), nullable=True, index=True)
    trigger_context = Column(JSON, nullable=True)
    status = Column(String(16), nullable=False, default="queued", index=True)
    scheduled_for = Column(DateTime, nullable=True, index=True)
    executed_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    idempotency_key = Column(String(120), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
