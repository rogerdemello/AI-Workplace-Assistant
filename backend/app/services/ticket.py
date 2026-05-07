import logging
import uuid
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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
        query = self.db.query(TicketMessage).filter(TicketMessage.ticket_id == ticket_id)
        if not is_hr:
            query = query.filter(TicketMessage.is_internal == 0)
        try:
            return query.order_by(TicketMessage.created_at.asc()).all()
        except (ProgrammingError, OperationalError):
            self.db.rollback()
            logger.warning(
                "ticket_messages ORM list failed; using column-safe fallback",
                exc_info=True,
            )
            rows = self.db.execute(
                text(
                    """
                    SELECT id, ticket_id, sender_id, message_text, created_at
                    FROM ticket_messages
                    WHERE ticket_id = :ticket_id
                    ORDER BY created_at ASC
                    """
                ),
                {"ticket_id": ticket_id},
            ).fetchall()
            out: List[TicketMessage] = []
            for r in rows:
                tm = TicketMessage(
                    id=r[0],
                    ticket_id=r[1],
                    sender_id=r[2],
                    message_text=r[3],
                    is_internal=0,
                )
                tm.created_at = r[4]
                out.append(tm)
            return out

    def add_message(self, ticket_id: UUID, sender_id: Optional[UUID], message_text: str, is_internal: bool = False) -> TicketMessage:
        message = TicketMessage(
            ticket_id=ticket_id,
            sender_id=sender_id,
            message_text=message_text,
            is_internal=1 if is_internal else 0,
        )
        try:
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            return message
        except (ProgrammingError, OperationalError):
            self.db.rollback()
            logger.warning("ticket_messages ORM insert degraded; retrying without is_internal", exc_info=True)
            mid = uuid.uuid4()
            now = self._utcnow_naive()
            try:
                self.db.execute(
                    text(
                        """
                        INSERT INTO ticket_messages (id, ticket_id, sender_id, message_text, created_at)
                        VALUES (:id, :ticket_id, :sender_id, :message_text, :created_at)
                        """
                    ),
                    {
                        "id": mid,
                        "ticket_id": ticket_id,
                        "sender_id": sender_id,
                        "message_text": message_text,
                        "created_at": now,
                    },
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception("ticket_messages fallback insert failed")
                raise
            out = TicketMessage(
                id=mid,
                ticket_id=ticket_id,
                sender_id=sender_id,
                message_text=message_text,
                is_internal=1 if is_internal else 0,
            )
            out.created_at = now
            return out

    def list_assignees(self) -> List[User]:
        """Return active HR/Admin users that can be assigned to tickets."""
        return (
            self.db.query(User)
            .filter(User.role.in_([UserRole.hr, UserRole.admin]))
            .filter(User.status == UserStatus.active)
            .order_by(User.name.asc())
            .all()
        )

    def list_related_tickets(self, ticket: Ticket, limit: int = 6) -> List[Ticket]:
        query = self.db.query(Ticket).filter(Ticket.id != ticket.id)

        if ticket.hash:
            query = query.filter(Ticket.hash == ticket.hash)
        else:
            query = query.filter(Ticket.category == ticket.category)

        return query.order_by(Ticket.created_at.desc()).limit(max(1, min(limit, 20))).all()
    
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
