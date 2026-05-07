import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String, UUID

from ..core.time import utcnow_naive
from ..database import Base


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False, index=True)
    event_type = Column(String(60), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    conditions = Column(JSON, nullable=False, default=dict)
    actions = Column(JSON, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, index=True)
