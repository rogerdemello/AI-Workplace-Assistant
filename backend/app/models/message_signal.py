from sqlalchemy import Column, DateTime, ForeignKey, String, UUID
import uuid

from ..core.time import utcnow_naive
from ..database import Base


class MessageSignal(Base):
    __tablename__ = "message_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False, index=True)
    emotion = Column(String(50), nullable=False, default="neutral", index=True)
    topic = Column(String(80), nullable=False, default="general", index=True)
    severity = Column(String(20), nullable=False, default="low", index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
