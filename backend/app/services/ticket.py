from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from ..models.ticket import Ticket, TicketMessage, TicketStatus, TicketPriority, SLA_HOURS
from ..models.user import User, UserRole, UserStatus

class TicketService:
    def __init__(self, db: Session):
        self.db = db
    
    @staticmethod
    def _utcnow_naive() -> datetime:
        """Return UTC now as naive datetime for DB-compatible comparisons."""
        return datetime.now(timezone.utc).replace(tzinfo=None)

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

    def create_ticket_with_dedup(
        self,
        user_id: UUID,
        query: str,
        category: str,
        priority: TicketPriority,
        sentiment_score: Optional[int] = None,
    ) -> Tuple[Ticket, bool]:
        import hashlib
        normalized = query.lower().strip()
        ticket_hash = hashlib.sha256(normalized.encode()).hexdigest()

        cutoff = self._utcnow_naive() - timedelta(hours=24)
        existing = (
            self.db.query(Ticket)
            .filter(Ticket.user_id == user_id)
            .filter(Ticket.hash == ticket_hash)
            .filter(Ticket.created_at >= cutoff)
            .filter(Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]))
            .first()
        )
        if existing:
            return existing, False

        ticket = Ticket(
            user_id=user_id,
            query=query,
            category=category,
            priority=priority,
            status=TicketStatus.open,
            hash=ticket_hash,
            sentiment_score=sentiment_score,
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket, True

    def has_recent_ticket(self, user_id: UUID, query: str, hours: int = 24) -> bool:
        import hashlib
        normalized = query.lower().strip()
        ticket_hash = hashlib.sha256(normalized.encode()).hexdigest()
        cutoff = self._utcnow_naive() - timedelta(hours=hours)
        return (
            self.db.query(Ticket)
            .filter(Ticket.user_id == user_id)
            .filter(Ticket.hash == ticket_hash)
            .filter(Ticket.created_at >= cutoff)
            .first()
        ) is not None
    
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
                ticket.resolved_at = self._utcnow_naive()
        
        if priority is not None:
            ticket.priority = priority
        
        if assigned_to is not None and is_hr:
            ticket.assigned_to = assigned_to
        
        self.db.commit()
        self.db.refresh(ticket)
        return ticket
    
    def list_messages(self, ticket_id: UUID, user_id: Optional[UUID], is_hr: bool = False) -> List[TicketMessage]:
        ticket = self.get_ticket(ticket_id, user_id, is_hr)
        if not ticket:
            return []
        return (
            self.db.query(TicketMessage)
            .filter(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at.asc())
            .all()
        )

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

    def list_assignees(self) -> List[User]:
        """Return active HR/Admin users that can be assigned to tickets."""
        return (
            self.db.query(User)
            .filter(User.role.in_([UserRole.hr, UserRole.admin]))
            .filter(User.status == UserStatus.active)
            .order_by(User.name.asc())
            .all()
        )
    
    def get_sla_due_at(self, ticket: Ticket) -> datetime:
        return ticket.sla_due_at
    
    def is_sla_warning(self, ticket: Ticket) -> bool:
        if ticket.status in [TicketStatus.resolved, TicketStatus.closed]:
            return False
        
        sla_hours = SLA_HOURS.get(ticket.priority, 24)
        sla_due = ticket.sla_due_at
        warning_time = sla_due - timedelta(hours=sla_hours * 0.2)  # 80% of SLA time
        now = self._utcnow_naive()
        return now >= warning_time and now < sla_due
    
    def is_sla_breached(self, ticket: Ticket) -> bool:
        if ticket.status in [TicketStatus.resolved, TicketStatus.closed]:
            return False
        
        sla_due = ticket.sla_due_at
        return self._utcnow_naive() > sla_due
