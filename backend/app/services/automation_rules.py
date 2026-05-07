from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.automation_rule import AutomationRule
from ..models.hr_notification import HrNotification
from ..models.leave_request import LeaveRequest
from ..models.ticket import Ticket, TicketPriority, TicketStatus
from ..models.ticket_action_log import TicketActionLog


class AutomationRulesService:
    def __init__(self, db: Session):
        self.db = db

    def list_rules(self) -> list[AutomationRule]:
        return self.db.query(AutomationRule).order_by(AutomationRule.created_at.desc()).all()

    def create_rule(
        self,
        *,
        name: str,
        event_type: str,
        conditions: dict[str, Any],
        actions: dict[str, Any],
        created_by: UUID | None,
    ) -> AutomationRule:
        rule = AutomationRule(
            name=name.strip(),
            event_type=event_type.strip(),
            enabled=True,
            conditions=conditions or {},
            actions=actions or {},
            created_by=created_by,
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def update_rule(self, rule_id: UUID, *, name: str | None, enabled: bool | None, conditions: dict[str, Any] | None, actions: dict[str, Any] | None) -> AutomationRule | None:
        rule = self.db.query(AutomationRule).filter(AutomationRule.id == rule_id).first()
        if not rule:
            return None
        if name is not None:
            rule.name = name.strip()
        if enabled is not None:
            rule.enabled = enabled
        if conditions is not None:
            rule.conditions = conditions
        if actions is not None:
            rule.actions = actions
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def apply_ticket_created_rules(self, ticket: Ticket, actor_id: UUID | None = None) -> list[str]:
        applied = self.apply_event_rules(
            event_type="ticket_created",
            context={"ticket": ticket, "actor_id": actor_id},
        )
        if applied:
            self.db.commit()
            self.db.refresh(ticket)
        return applied

    def apply_ticket_updated_rules(
        self,
        ticket: Ticket,
        *,
        previous_status: str | None = None,
        actor_id: UUID | None = None,
    ) -> list[str]:
        applied = self.apply_event_rules(
            event_type="ticket_updated",
            context={
                "ticket": ticket,
                "actor_id": actor_id,
                "previous_status": previous_status,
                "current_status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
            },
        )
        if applied:
            self.db.commit()
            self.db.refresh(ticket)
        return applied

    def apply_leave_reviewed_rules(
        self,
        leave: LeaveRequest,
        *,
        actor_id: UUID | None = None,
    ) -> list[str]:
        applied = self.apply_event_rules(
            event_type="leave_reviewed",
            context={"leave": leave, "actor_id": actor_id},
        )
        if applied:
            self.db.commit()
            self.db.refresh(leave)
        return applied

    def apply_event_rules(self, *, event_type: str, context: dict[str, Any]) -> list[str]:
        rules = (
            self.db.query(AutomationRule)
            .filter(AutomationRule.enabled == True, AutomationRule.event_type == event_type)
            .all()
        )
        applied: list[str] = []
        for rule in rules:
            if not self._matches(rule.conditions or {}, context):
                continue
            self._apply_actions(context=context, actions=rule.actions or {})
            applied.append(rule.name)
        return applied

    def _matches(self, conditions: dict[str, Any], context: dict[str, Any]) -> bool:
        ticket = context.get("ticket")
        leave = context.get("leave")
        signal = context.get("signal")
        mood = str(context.get("mood") or "").lower()

        category_in = conditions.get("category_in")
        if ticket is not None and isinstance(category_in, list) and category_in:
            if ticket.category not in [str(v) for v in category_in]:
                return False

        priority_in = conditions.get("priority_in")
        if ticket is not None and isinstance(priority_in, list) and priority_in:
            priority_value = ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority)
            if priority_value not in [str(v) for v in priority_in]:
                return False

        to_status_in = conditions.get("to_status_in")
        if ticket is not None and isinstance(to_status_in, list) and to_status_in:
            current_status = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
            if current_status not in [str(v) for v in to_status_in]:
                return False

        from_status_in = conditions.get("from_status_in")
        if ticket is not None and isinstance(from_status_in, list) and from_status_in:
            previous_status = str(context.get("previous_status") or "")
            if previous_status and previous_status not in [str(v) for v in from_status_in]:
                return False

        leave_status_in = conditions.get("leave_status_in")
        if leave is not None and isinstance(leave_status_in, list) and leave_status_in:
            leave_status = leave.status.value if hasattr(leave.status, "value") else str(leave.status)
            if leave_status not in [str(v) for v in leave_status_in]:
                return False

        signal_triage_in = conditions.get("signal_triage_in")
        if signal is not None and isinstance(signal_triage_in, list) and signal_triage_in:
            triage = str(signal.get("triage_level") or "")
            if triage not in [str(v) for v in signal_triage_in]:
                return False

        mood_in = conditions.get("mood_in")
        if isinstance(mood_in, list) and mood_in:
            if mood not in [str(v).lower() for v in mood_in]:
                return False

        return True

    def _apply_actions(self, *, context: dict[str, Any], actions: dict[str, Any]) -> None:
        ticket = context.get("ticket")
        leave = context.get("leave")
        actor_id = context.get("actor_id")
        user_id = context.get("user_id")

        new_priority = actions.get("set_priority")
        if ticket is not None and isinstance(new_priority, str) and new_priority in {p.value for p in TicketPriority}:
            ticket.priority = TicketPriority(new_priority)
            self.db.add(TicketActionLog(ticket_id=ticket.id, actor_id=actor_id, action_type="automation_set_priority", details=new_priority))

        assign_user = actions.get("assign_to_user_id")
        if ticket is not None and isinstance(assign_user, str) and assign_user.strip():
            try:
                ticket.assigned_to = UUID(assign_user)
                self.db.add(TicketActionLog(ticket_id=ticket.id, actor_id=actor_id, action_type="automation_assign", details=assign_user))
            except Exception:
                pass

        set_status = actions.get("set_status")
        if ticket is not None and isinstance(set_status, str) and set_status in {s.value for s in TicketStatus}:
            ticket.status = TicketStatus(set_status)
            self.db.add(TicketActionLog(ticket_id=ticket.id, actor_id=actor_id, action_type="automation_set_status", details=set_status))

        if ticket is not None and actions.get("auto_escalate") is True:
            ticket.status = TicketStatus.escalated
            ticket.priority = TicketPriority.critical
            self.db.add(TicketActionLog(ticket_id=ticket.id, actor_id=actor_id, action_type="automation_escalate", details="auto_escalate=true"))

        review_comment_template = actions.get("set_review_comment_template")
        if leave is not None and isinstance(review_comment_template, str) and review_comment_template.strip():
            leave_status = leave.status.value if hasattr(leave.status, "value") else str(leave.status)
            leave.review_comment = review_comment_template.format(
                status=leave_status,
                leave_id=str(leave.id),
            )

        if leave is not None and actions.get("notify_hr") is True:
            leave_status = leave.status.value if hasattr(leave.status, "value") else str(leave.status)
            title = str(actions.get("notification_title") or "Leave review completed")
            body_template = str(actions.get("notification_body_template") or "Leave {leave_id} reviewed with status {status}.")
            body = body_template.format(leave_id=str(leave.id), status=leave_status)
            self.db.add(
                HrNotification(
                    ticket_id=None,
                    actor_id=actor_id,
                    title=title,
                    body=body,
                    notification_type="leave_reviewed",
                    severity=str(actions.get("notification_severity") or "info"),
                )
            )

        if actions.get("create_hr_notification") is True:
            signal = context.get("signal") or {}
            title = str(actions.get("notification_title") or "Automation alert")
            body_template = str(actions.get("notification_body_template") or "Automated event captured for user {user_id}.")
            body = body_template.format(
                user_id=str(user_id) if user_id else "unknown",
                ticket_id=str(ticket.id) if ticket is not None else "",
                leave_id=str(leave.id) if leave is not None else "",
                mood=str(context.get("mood") or ""),
                triage_level=str(signal.get("triage_level") or ""),
            )
            self.db.add(
                HrNotification(
                    ticket_id=ticket.id if ticket is not None else None,
                    actor_id=actor_id,
                    title=title,
                    body=body,
                    notification_type=str(actions.get("notification_type") or "automation_event"),
                    severity=str(actions.get("notification_severity") or "info"),
                )
            )
