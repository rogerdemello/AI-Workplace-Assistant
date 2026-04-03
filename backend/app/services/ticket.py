from typing import List, Optional, Union
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models.ticket import Ticket, TicketMessage, TicketStatus, TicketPriority, SLA_HOURS

class TicketService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_ticket(self, user_id: UUID, query: str, category: str, priority: TicketPriority) -> Ticket:
        ticket = Ticket(
            user_id=user_id,
            query=query,
            category=category,
            priority=priority,
            status=TicketStatus.open
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket
    
    def get_tickets(self, user_id: Optional[UUID] = None, status: Optional[TicketStatus] = None, 
                    assigned_to: Optional[UUID] = None, is_hr: bool = False) -> List[Ticket]:
        query = self.db.query(Ticket)
        
        if not is_hr and user_id is not None:
            query = query.filter(Ticket.user_id == user_id)
        
        if status is not None:
            query = query.filter(Ticket.status == status)
        
        if assigned_to is not None:
            query = query.filter(Ticket.assigned_to == assigned_to)
        
        return query.order_by(Ticket.created_at.desc()).all()
    
    def get_ticket(self, ticket_id: UUID, user_id: Optional[UUID], is_hr: bool = False) -> Optional[Ticket]:
        query = self.db.query(Ticket).filter(Ticket.id == ticket_id)
        
        if not is_hr and user_id is not None:
            query = query.filter(Ticket.user_id == user_id)
        
        return query.first()
    
    def update_ticket(self, ticket_id: UUID, user_id: Optional[UUID], is_hr: bool = False,
                      status: Optional[TicketStatus] = None, priority: Optional[TicketPriority] = None,
                      assigned_to: Optional[UUID] = None) -> Optional[Ticket]:
        ticket = self.get_ticket(ticket_id, user_id, is_hr)
        
        if not ticket:
            return None
        
        if status is not None:
            ticket.status = status
            if status == TicketStatus.resolved:
                ticket.resolved_at = datetime.utcnow()
        
        if priority is not None:
            ticket.priority = priority
        
        if assigned_to is not None and is_hr:
            ticket.assigned_to = assigned_to
        
        self.db.commit()
        self.db.refresh(ticket)
        return ticket
    
    def add_message(self, ticket_id: UUID, sender_id: Optional[UUID], message_text: str) -> TicketMessage:
        message = TicketMessage(
            ticket_id=ticket_id,
            sender_id=sender_id,
            message_text=message_text
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message
    
    def get_sla_due_at(self, ticket: Ticket) -> datetime:
        sla_hours = SLA_HOURS.get(ticket.priority, 24)
        return ticket.created_at + timedelta(hours=sla_hours)
    
    def is_sla_warning(self, ticket: Ticket) -> bool:
        if ticket.status in [TicketStatus.resolved, TicketStatus.closed]:
            return False
        
        sla_hours = SLA_HOURS.get(ticket.priority, 24)
        sla_due = self.get_sla_due_at(ticket)
        warning_time = sla_due - timedelta(hours=sla_hours * 0.2)  # 80% of SLA time
        return datetime.utcnow() >= warning_time and datetime.utcnow() < sla_due
    
    def is_sla_breached(self, ticket: Ticket) -> bool:
        if ticket.status in [TicketStatus.resolved, TicketStatus.closed]:
            return False
        
        sla_due = self.get_sla_due_at(ticket)
        return datetime.utcnow() > sla_due
