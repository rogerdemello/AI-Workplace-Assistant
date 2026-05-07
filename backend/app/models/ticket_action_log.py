from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Text
import uuid

from ..database import Base
from ..core.time import utcnow_naive


class TicketActionLog(Base):
    __tablename__ = "ticket_action_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action_type = Column(String(64), nullable=False, index=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
