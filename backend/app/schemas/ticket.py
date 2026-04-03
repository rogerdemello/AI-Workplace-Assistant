from pydantic import BaseModel
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

class TicketCreate(BaseModel):
    query: str
    category: str
    priority: TicketPriority = TicketPriority.medium

class TicketUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_to: Optional[UUID] = None

class TicketMessageCreate(BaseModel):
    message_text: str

class TicketResponse(BaseModel):
    id: UUID
    user_id: UUID
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
    
    class Config:
        from_attributes = True

class TicketMessageResponse(BaseModel):
    id: UUID
    ticket_id: UUID
    sender_id: Optional[UUID] = None
    message_text: str
    created_at: datetime
    
    class Config:
        from_attributes = True
