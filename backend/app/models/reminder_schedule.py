from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Text, JSON
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class ReminderSchedule(Base):
    __tablename__ = "reminder_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    reminder_type = Column(String(32), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    schedule_kind = Column(String(16), nullable=False, default="one_time", index=True)
    run_at = Column(DateTime, nullable=True, index=True)
    cron_expr = Column(String(120), nullable=True)
    timezone = Column(String(64), nullable=False, default="UTC")
    status = Column(String(16), nullable=False, default="active", index=True)
    last_triggered_at = Column(DateTime, nullable=True)
    next_trigger_at = Column(DateTime, nullable=True, index=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
