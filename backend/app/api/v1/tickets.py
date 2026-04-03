from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ...database import get_db
from ...schemas.ticket import (
    TicketCreate, TicketUpdate, TicketResponse, 
    TicketMessageCreate, TicketMessageResponse
)
from ...auth import get_current_user
from ...models.user import User
from ...models.ticket import TicketStatus
from ...services.ticket import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])

def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    return TicketService(db)

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
    service: TicketService = Depends(get_ticket_service)
):
    new_ticket = service.create_ticket(
        user_id=current_user.id,
        query=ticket.query,
        category=ticket.category,
        priority=ticket.priority
    )
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
