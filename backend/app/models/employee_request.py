"""Structured employee requests raised conversationally through Mark.

One table backs every "ask HR for something" flow that isn't already a leave
request or a ticket: booking a 1:1 appointment, claiming an expense, asking for
a WFH day or shift swap, and requesting a document. They share the same
lifecycle (employee submits → HR actions it), so they share a table and a single
HR review surface; the per-type slots live in ``details``.
"""

from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Date, Enum as SQLEnum, Text, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
import enum

from ..database import Base
from ..core.time import utcnow_naive


class RequestType(str, enum.Enum):
    appointment = "appointment"
    expense = "expense"
    shift_change = "shift_change"
    document = "document"


class RequestStatus(str, enum.Enum):
    pending = "pending"
    scheduled = "scheduled"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    completed = "completed"


#: Statuses an employee-facing request can no longer move out of.
TERMINAL_STATUSES = {
    RequestStatus.rejected,
    RequestStatus.cancelled,
    RequestStatus.completed,
}


class EmployeeRequest(Base):
    __tablename__ = "employee_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    request_type = Column(SQLEnum(RequestType), nullable=False, index=True)
    status = Column(SQLEnum(RequestStatus), default=RequestStatus.pending, nullable=False, index=True)

    title = Column(String(255), nullable=False)
    #: Per-type slots collected by the chat flow (topic, document_type, ...).
    details = Column(JSONB, nullable=False, default=dict)

    #: appointment — when HR and the employee agreed to meet.
    scheduled_at = Column(DateTime, nullable=True, index=True)
    #: shift_change — the window the employee wants changed.
    start_date = Column(Date, nullable=True, index=True)
    end_date = Column(Date, nullable=True)
    #: expense — claim value, currency held in ``details``.
    amount = Column(Numeric(12, 2), nullable=True)

    handled_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    handled_at = Column(DateTime, nullable=True)
    hr_note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    handler = relationship("User", foreign_keys=[handled_by])
