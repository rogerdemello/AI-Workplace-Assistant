import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UUID

from ..core.time import utcnow_naive
from ..database import Base


class HrNotification(Base):
    __tablename__ = "hr_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=True, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String(180), nullable=False)
    body = Column(Text, nullable=True)
    notification_type = Column(String(48), nullable=False, default="ticket_update", index=True)
    severity = Column(String(24), nullable=False, default="info", index=True)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    read_at = Column(DateTime, nullable=True)
