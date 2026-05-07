from sqlalchemy import Column, Integer, String, UUID, ForeignKey, DateTime, Enum as SQLEnum, Text, UniqueConstraint
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timedelta
import enum

from ..database import Base
from ..core.time import utcnow_naive

class TicketStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    escalated = "escalated"
    closed = "closed"

class TicketPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

SLA_HOURS = {
    TicketPriority.critical: 4,
    TicketPriority.high: 8,
    TicketPriority.medium: 24,
    TicketPriority.low: 72
}

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    query = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    status = Column(SQLEnum(TicketStatus), default=TicketStatus.open, index=True)
    priority = Column(SQLEnum(TicketPriority), default=TicketPriority.medium, index=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    resolved_at = Column(DateTime, nullable=True)
    hash = Column(String(64), nullable=True, index=True)
    sentiment_score = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "hash", name="uq_ticket_user_hash"),
    )

    @property
    def sla_due_at(self):
        sla_hours = SLA_HOURS.get(self.priority, 24)
        return self.created_at + timedelta(hours=sla_hours)

    user = relationship("User", foreign_keys=[user_id])
    assigned_user = relationship("User", foreign_keys=[assigned_to])
    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")

class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False, index=True)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    message_text = Column(Text, nullable=False)
    is_internal = Column(Integer, default=0, nullable=False, index=True)  # 1 = HR-only note
    created_at = Column(DateTime, default=utcnow_naive, index=True)

    ticket = relationship("Ticket", back_populates="messages")
