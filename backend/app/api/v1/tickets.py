from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ...core.feature_flags import get_feature_flags
from ...database import get_db
from ...schemas.ticket import (
    TicketCreate, TicketUpdate, TicketResponse,
    TicketMessageCreate, TicketMessageResponse, TicketAssigneeResponse
)
from ...events import event_bus
from ...events.events import DomainEvent, EVENT_TICKET_CREATED
from ...auth import get_current_user
from ...models.user import User
from ...models.ticket import TicketStatus, TicketPriority
from ...services.ticket import TicketService
from ...services.tickets.ticket_action_service import TicketActionService

router = APIRouter(prefix="/tickets", tags=["tickets"])

HARASSMENT_KEYWORDS = {
    "harass", "harassment", "bully", "bullying", "sexual", "abuse",
    "threat", "discriminat", "discrimination", "assault", "molest"
}


def _compute_ticket_priority(query: str, category: str, user_id: UUID, service: TicketService) -> TicketPriority:
    query_lower = query.lower()
    if any(kw in query_lower for kw in HARASSMENT_KEYWORDS):
        return TicketPriority.critical
    if category == "complaint":
        return TicketPriority.high
    if service.has_recent_ticket(user_id, query):
        return TicketPriority.high
    if category == "leave":
        return TicketPriority.medium
    return TicketPriority.low

def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    return TicketService(db)


def get_ticket_action_service(db: Session = Depends(get_db)) -> TicketActionService:
    return TicketActionService(db)

def enrich_ticket_response(ticket, service: TicketService) -> dict:
    """Enrich ticket response with SLA information."""
    from datetime import datetime
    
    response = {
        "id": ticket.id,
        "user_id": ticket.user_id,
        "query": ticket.query,
        "category": ticket.category,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": ticket.assigned_to,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "resolved_at": ticket.resolved_at,
    }
    
    # Add SLA information
    if ticket.status not in [TicketStatus.resolved, TicketStatus.closed]:
        response["sla_due_at"] = service.get_sla_due_at(ticket)
        response["sla_warning"] = service.is_sla_warning(ticket)
    else:
        response["sla_due_at"] = None
        response["sla_warning"] = False
    
    return response

@router.post("", response_model=TicketResponse)
def create_ticket(
    ticket: TicketCreate,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
    action_service: TicketActionService = Depends(get_ticket_action_service),
):
    if "priority" in ticket.model_fields_set and ticket.priority is not None:
        priority = ticket.priority
    else:
        priority = _compute_ticket_priority(ticket.query, ticket.category, current_user.id, service)

    # Harassment keywords always override to critical regardless of explicit priority
    if any(kw in ticket.query.lower() for kw in HARASSMENT_KEYWORDS):
        priority = TicketPriority.critical

    try:
        new_ticket, is_new = service.create_ticket_with_dedup(
            user_id=current_user.id,
            query=ticket.query,
            category=ticket.category,
            priority=priority,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create ticket")

    if is_new:
        action_service.auto_assign_ticket(new_ticket)

    try:
        event_bus.publish(
            DomainEvent(
                name=EVENT_TICKET_CREATED,
                payload={
                    "ticket_id": str(new_ticket.id),
                    "user_id": str(current_user.id),
                    "priority": new_ticket.priority.value,
                    "category": new_ticket.category,
                },
            )
        )
    except Exception:
        pass
    return enrich_ticket_response(new_ticket, service)

@router.get("", response_model=List[TicketResponse])
def get_tickets(
    status: Optional[TicketStatus] = None,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service)
):
    is_hr = current_user.role in ["hr", "admin"]
    tickets = service.get_tickets(
        user_id=current_user.id,
        status=status,
        is_hr=is_hr
    )
    return [enrich_ticket_response(t, service) for t in tickets]


@router.get("/assignees", response_model=List[TicketAssigneeResponse])
def list_ticket_assignees(
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service)
):
    is_hr = current_user.role in ["hr", "admin"]
    if not is_hr:
        raise HTTPException(status_code=403, detail="Only HR/Admin can list assignees")

    assignees = service.list_assignees()
    return [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        }
        for user in assignees
    ]


class TicketAssignRequest(BaseModel):
    assignee_id: UUID


class TicketBulkActionRequest(BaseModel):
    ticket_ids: List[UUID] = Field(default_factory=list)
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_to: Optional[UUID] = None


@router.post("/bulk-action", response_model=List[TicketResponse])
def bulk_update_tickets(
    payload: TicketBulkActionRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
    action_service: TicketActionService = Depends(get_ticket_action_service),
):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(status_code=403, detail="Only HR/Admin can perform bulk actions")

    if not get_feature_flags().enable_ticket_bulk_actions:
        raise HTTPException(status_code=503, detail="Bulk ticket actions are disabled")

    updated = action_service.bulk_update(
        ticket_ids=payload.ticket_ids,
        status=payload.status,
        priority=payload.priority,
        assigned_to=payload.assigned_to,
    )
    return [enrich_ticket_response(ticket, service) for ticket in updated]


@router.post("/{ticket_id}/assign", response_model=TicketResponse)
def assign_ticket(
    ticket_id: UUID,
    payload: TicketAssignRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
    action_service: TicketActionService = Depends(get_ticket_action_service),
):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(status_code=403, detail="Only HR/Admin can assign tickets")

    ticket = action_service.assign_ticket(ticket_id=ticket_id, assignee_id=payload.assignee_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return enrich_ticket_response(ticket, service)


@router.post("/{ticket_id}/enforce-sla", response_model=TicketResponse)
def enforce_ticket_sla(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
    action_service: TicketActionService = Depends(get_ticket_action_service),
):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(status_code=403, detail="Only HR/Admin can enforce SLA")

    ticket = action_service.enforce_sla(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return enrich_ticket_response(ticket, service)

@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service)
):
    is_hr = current_user.role in ["hr", "admin"]
    ticket = service.get_ticket(ticket_id, current_user.id, is_hr)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return enrich_ticket_response(ticket, service)

@router.patch("/{ticket_id}", response_model=TicketResponse)
def update_ticket(
    ticket_id: UUID,
    ticket_update: TicketUpdate,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service)
):
    is_hr = current_user.role in ["hr", "admin"]
    ticket = service.update_ticket(
        ticket_id=ticket_id,
        user_id=current_user.id,
        is_hr=is_hr,
        status=ticket_update.status,
        priority=ticket_update.priority,
        assigned_to=ticket_update.assigned_to
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return enrich_ticket_response(ticket, service)

@router.get("/{ticket_id}/messages", response_model=List[TicketMessageResponse])
def list_ticket_messages(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service)
):
    is_hr = current_user.role in ["hr", "admin"]
    messages = service.list_messages(ticket_id, current_user.id, is_hr)
    if not messages and not service.get_ticket(ticket_id, current_user.id, is_hr):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return messages


@router.post("/{ticket_id}/messages", response_model=TicketMessageResponse)
def add_ticket_message(
    ticket_id: UUID,
    message: TicketMessageCreate,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service)
):
    is_hr = current_user.role in ["hr", "admin"]
    ticket = service.get_ticket(ticket_id, current_user.id, is_hr)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    msg = service.add_message(ticket_id, current_user.id, message.message_text)
    return msg


@router.post("/sla-scan/trigger")
def trigger_sla_scan():
    from ...services.scheduler import check_and_escalate_sla_breached_tickets
    result = check_and_escalate_sla_breached_tickets()
    return result
