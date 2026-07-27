from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Dict, Optional
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class RequestType(str, Enum):
    appointment = "appointment"
    expense = "expense"
    shift_change = "shift_change"
    document = "document"


class RequestStatus(str, Enum):
    pending = "pending"
    scheduled = "scheduled"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    completed = "completed"


class EmployeeRequestCreate(BaseModel):
    request_type: RequestType
    title: str = Field(min_length=2, max_length=255)
    details: Dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    amount: Optional[Decimal] = Field(default=None, ge=0)


class EmployeeRequestDecision(BaseModel):
    """HR action on a request. ``scheduled_at`` only applies to appointments."""

    hr_note: Optional[str] = Field(default=None, max_length=2000)
    scheduled_at: Optional[datetime] = None


class EmployeeRequestResponse(BaseModel):
    id: UUID
    user_id: UUID
    request_type: RequestType
    status: RequestStatus
    title: str
    details: Dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    amount: Optional[Decimal] = None
    handled_by: Optional[UUID] = None
    handled_at: Optional[datetime] = None
    hr_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    employee_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EmployeeRequestSummary(BaseModel):
    """Counts for the HR dashboard tiles."""

    pending: int = 0
    scheduled: int = 0
    approved: int = 0
    rejected: int = 0
    cancelled: int = 0
    completed: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)
