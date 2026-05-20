from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum

class TicketStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    escalated = "escalated"
    closed = "closed"

class TicketPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class TicketCategory(str, Enum):
    general = "general"
    leave = "leave"
    payroll = "payroll"
    benefits = "benefits"
    it_support = "it_support"
    complaint = "complaint"
    policy = "policy"
    hr = "hr"
    it = "it"
    facilities = "facilities"
    finance = "finance"
    management = "management"

class TicketCreate(BaseModel):
    query: str
    category: TicketCategory
    priority: TicketPriority = TicketPriority.medium

    @field_validator('query')
    @classmethod
    def query_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Query must be a non-empty string')
        return v

class TicketUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_to: Optional[UUID] = None

class TicketMessageCreate(BaseModel):
    message_text: str

class TicketResponse(BaseModel):
    id: UUID
    # Nullable because anonymous tickets scrub the submitter id before the
    # response leaves the server. Non-anonymous tickets always populate it.
    user_id: Optional[UUID] = None
    is_anonymous: bool = False
    query: str
    category: str
    status: TicketStatus
    priority: TicketPriority
    assigned_to: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    sla_due_at: Optional[datetime] = None
    sla_warning: bool = False

    model_config = ConfigDict(from_attributes=True)

class TicketMessageResponse(BaseModel):
    id: UUID
    ticket_id: UUID
    sender_id: Optional[UUID] = None
    message_text: str
    is_internal: bool = False
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class TicketAssigneeResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class TicketActionLogResponse(BaseModel):
    id: UUID
    ticket_id: UUID
    actor_id: Optional[UUID] = None
    action_type: str
    details: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
