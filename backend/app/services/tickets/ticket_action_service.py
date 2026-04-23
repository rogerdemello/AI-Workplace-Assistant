"""Action-oriented ticket operations for HR dashboards and SLA workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ...models.ticket import Ticket, TicketPriority, TicketStatus
from ..ticket import TicketService


class TicketActionService:
    _round_robin_index: int = 0

    def __init__(self, db: Session):
        self.db = db
        self.ticket_service = TicketService(db)

    @staticmethod
    def _utcnow_naive() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def auto_assign_ticket(self, ticket: Ticket) -> Ticket:
        from ...models.user import User, UserRole, UserStatus

        if ticket.category in {"management", "complaint"}:
            hr_user = (
                self.db.query(User)
                .filter(User.role.in_([UserRole.hr, UserRole.admin]))
                .filter(User.status == UserStatus.active)
                .order_by(User.created_at.asc())
                .first()
            )
            if hr_user:
                ticket.assigned_to = hr_user.id

        elif ticket.category == "leave":
            user = self.db.query(User).filter(User.id == ticket.user_id).first()
            if user and user.manager_id:
                ticket.assigned_to = user.manager_id

        else:
            hr_users = (
                self.db.query(User)
                .filter(User.role.in_([UserRole.hr, UserRole.admin]))
                .filter(User.status == UserStatus.active)
                .order_by(User.id.asc())
                .all()
            )
            if hr_users:
                idx = TicketActionService._round_robin_index % len(hr_users)
                ticket.assigned_to = hr_users[idx].id
                TicketActionService._round_robin_index += 1

        if ticket.assigned_to and ticket.status == TicketStatus.open:
            ticket.status = TicketStatus.in_progress

        ticket.updated_at = self._utcnow_naive()
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def assign_ticket(self, ticket_id: UUID, assignee_id: UUID) -> Optional[Ticket]:
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return None
        ticket.assigned_to = assignee_id
        ticket.updated_at = self._utcnow_naive()
        if ticket.status == TicketStatus.open:
            ticket.status = TicketStatus.in_progress
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def enforce_sla(self, ticket_id: UUID) -> Optional[Ticket]:
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return None

        if self.ticket_service.is_sla_breached(ticket) and ticket.status not in {
            TicketStatus.resolved,
            TicketStatus.closed,
        }:
            ticket.status = TicketStatus.escalated
            if ticket.priority in {TicketPriority.low, TicketPriority.medium}:
                ticket.priority = TicketPriority.high
            ticket.updated_at = self._utcnow_naive()
            self.db.commit()
            self.db.refresh(ticket)
        return ticket

    def bulk_update(
        self,
        ticket_ids: List[UUID],
        *,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        assigned_to: Optional[UUID] = None,
    ) -> List[Ticket]:
        if not ticket_ids:
            return []

        tickets = self.db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all()
        now = self._utcnow_naive()

        for ticket in tickets:
            if status is not None:
                ticket.status = status
                if status == TicketStatus.resolved:
                    ticket.resolved_at = now
            if priority is not None:
                ticket.priority = priority
            if assigned_to is not None:
                ticket.assigned_to = assigned_to
            ticket.updated_at = now

        self.db.commit()
        for ticket in tickets:
            self.db.refresh(ticket)
        return tickets
