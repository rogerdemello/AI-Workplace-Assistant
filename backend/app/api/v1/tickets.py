from datetime import datetime, timedelta, timezone
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ...core.feature_flags import get_feature_flags
from ...database import get_db
from ...schemas.ticket import (
    TicketCreate, TicketUpdate, TicketResponse,
    TicketMessageCreate, TicketMessageResponse, TicketAssigneeResponse, TicketActionLogResponse
)
from ...events import event_bus
from ...events.events import DomainEvent, EVENT_TICKET_CREATED
from ...auth import get_current_user
from ...auth.rbac import require_roles
from ...models.user import User
from ...models.ticket import TicketStatus, TicketPriority
from ...models.action import HRAction, HRActionStatus
from ...models.ticket_action_log import TicketActionLog
from ...models.hr_notification import HrNotification
from ...services.ticket import TicketService
from ...services.automation_rules import AutomationRulesService
from ...services.tickets.ticket_action_service import TicketActionService
from ...services.realtime_bus import realtime_bus
from ...services.v2.whatsapp_notify import notify_ticket_update

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
    """Enrich ticket response with SLA information.

    For anonymous tickets, the submitter ``user_id`` is scrubbed before the
    response leaves the server. The flag itself is preserved so the UI can
    render an "Anonymous reporter" placeholder explicitly.
    """
    is_anonymous = bool(getattr(ticket, "is_anonymous", False))

    response = {
        "id": ticket.id,
        "user_id": None if is_anonymous else ticket.user_id,
        "is_anonymous": is_anonymous,
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


def _log_ticket_action(db: Session, ticket_id: UUID, actor_id: UUID | None, action_type: str, details: str | None = None) -> None:
    try:
        db.add(TicketActionLog(ticket_id=ticket_id, actor_id=actor_id, action_type=action_type, details=details))
        db.commit()
    except Exception:
        db.rollback()


def _notify_hr(
    db: Session,
    ticket_id: UUID,
    actor_id: UUID | None,
    title: str,
    body: str | None = None,
    notification_type: str = "ticket_update",
    severity: str = "info",
) -> None:
    try:
        db.add(
            HrNotification(
                ticket_id=ticket_id,
                actor_id=actor_id,
                title=title,
                body=body,
                notification_type=notification_type,
                severity=severity,
            )
        )
        db.commit()
    except Exception:
        db.rollback()


def _publish_hr_realtime(event_type: str, payload: dict) -> None:
    try:
        asyncio.run(realtime_bus.publish(event_type, payload))
    except Exception:
        pass

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
            AutomationRulesService(service.db).apply_ticket_created_rules(new_ticket, actor_id=current_user.id)
        except Exception:
            service.db.rollback()
        _notify_hr(
            service.db,
            new_ticket.id,
            current_user.id,
            title="New ticket raised",
            body=(ticket.query or "")[:180],
            notification_type="ticket_created",
            severity="info",
        )
        _publish_hr_realtime(
            "hr_ticket_created",
            {
                "ticket_id": str(new_ticket.id),
                "user_id": str(new_ticket.user_id),
                "priority": str(new_ticket.priority.value if hasattr(new_ticket.priority, "value") else new_ticket.priority),
                "category": str(new_ticket.category),
            },
        )

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


class TicketEscalateRequest(BaseModel):
    reason: Optional[str] = "Escalated by HR"


class TicketScheduleCheckinRequest(BaseModel):
    scheduled_at: Optional[datetime] = None
    notes: Optional[str] = None


class TicketActionResponse(BaseModel):
    detail: str


class TicketCloseRequest(BaseModel):
    resolution_note: Optional[str] = "Resolved by HR"


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
    _log_ticket_action(service.db, ticket.id, current_user.id, "reassign", f"assigned_to={payload.assignee_id}")
    _notify_hr(
        service.db,
        ticket.id,
        current_user.id,
        title="Ticket reassigned",
        body=f"Ticket reassigned to {payload.assignee_id}",
        notification_type="ticket_reassigned",
        severity="info",
    )
    try:
        AutomationRulesService(service.db).apply_event_rules(
            event_type="ticket_reassigned",
            context={
                "ticket": ticket,
                "actor_id": current_user.id,
                "user_id": ticket.user_id,
                "assignee_id": payload.assignee_id,
            },
        )
        service.db.commit()
    except Exception:
        service.db.rollback()
    _publish_hr_realtime(
        "hr_ticket_reassigned",
        {"ticket_id": str(ticket.id), "assignee_id": str(payload.assignee_id)},
    )
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


@router.post("/{ticket_id}/escalate", response_model=TicketResponse)
def escalate_ticket(
    ticket_id: UUID,
    payload: TicketEscalateRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(status_code=403, detail="Only HR/Admin can escalate tickets")

    existing = service.get_ticket(ticket_id, current_user.id, is_hr=True)
    previous_status = (
        existing.status.value if existing and hasattr(existing.status, "value") else str(existing.status) if existing else None
    )
    ticket = service.update_ticket(
        ticket_id=ticket_id,
        user_id=current_user.id,
        is_hr=True,
        status=TicketStatus.escalated,
        priority=TicketPriority.critical,
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    service.add_message(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message_text=(payload.reason or "Escalated by HR"),
    )
    _log_ticket_action(service.db, ticket.id, current_user.id, "escalate", payload.reason or "Escalated by HR")
    _notify_hr(
        service.db,
        ticket.id,
        current_user.id,
        title="Ticket escalated",
        body=payload.reason or "Escalated by HR",
        notification_type="ticket_escalated",
        severity="high",
    )
    try:
        AutomationRulesService(service.db).apply_ticket_updated_rules(
            ticket,
            previous_status=previous_status,
            actor_id=current_user.id,
        )
        AutomationRulesService(service.db).apply_event_rules(
            event_type="ticket_escalated",
            context={
                "ticket": ticket,
                "actor_id": current_user.id,
                "user_id": ticket.user_id,
            },
        )
        service.db.commit()
    except Exception:
        service.db.rollback()
    _publish_hr_realtime("hr_ticket_escalated", {"ticket_id": str(ticket.id)})
    return enrich_ticket_response(ticket, service)


@router.post("/{ticket_id}/schedule-checkin", response_model=TicketActionResponse)
def schedule_ticket_checkin(
    ticket_id: UUID,
    payload: TicketScheduleCheckinRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(status_code=403, detail="Only HR/Admin can schedule check-ins")

    ticket = service.get_ticket(ticket_id, current_user.id, is_hr=True)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    action = HRAction(
        employee_id=ticket.user_id,
        action_type="schedule_checkin",
        status=HRActionStatus.pending,
        scheduled_at=payload.scheduled_at,
        created_by=current_user.id,
        notes=payload.notes or "Scheduled from ticket panel",
    )
    service.db.add(action)
    service.db.commit()

    service.add_message(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message_text=f"HR scheduled check-in ({action.id})",
    )
    _log_ticket_action(service.db, ticket.id, current_user.id, "schedule_checkin", payload.notes or "Scheduled check-in")
    _notify_hr(
        service.db,
        ticket.id,
        current_user.id,
        title="Check-in scheduled",
        body=payload.notes or "Scheduled check-in from ticket",
        notification_type="ticket_checkin",
        severity="info",
    )
    try:
        AutomationRulesService(service.db).apply_event_rules(
            event_type="ticket_checkin_scheduled",
            context={
                "ticket": ticket,
                "actor_id": current_user.id,
                "user_id": ticket.user_id,
                "notes": payload.notes or "",
            },
        )
        service.db.commit()
    except Exception:
        service.db.rollback()
    _publish_hr_realtime("hr_ticket_checkin_scheduled", {"ticket_id": str(ticket.id)})

    return {"detail": "Check-in scheduled and linked to ticket timeline."}


@router.post("/{ticket_id}/internal-notes", response_model=TicketMessageResponse)
def add_internal_note(
    ticket_id: UUID,
    message: TicketMessageCreate,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(status_code=403, detail="Only HR/Admin can add internal notes")

    ticket = service.get_ticket(ticket_id, current_user.id, is_hr=True)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msg = service.add_message(ticket_id, current_user.id, message.message_text, is_internal=True)
    _log_ticket_action(service.db, ticket.id, current_user.id, "internal_note", message.message_text)
    _notify_hr(
        service.db,
        ticket.id,
        current_user.id,
        title="Internal note added",
        body=message.message_text,
        notification_type="ticket_internal_note",
        severity="info",
    )
    try:
        AutomationRulesService(service.db).apply_event_rules(
            event_type="ticket_internal_note_added",
            context={
                "ticket": ticket,
                "actor_id": current_user.id,
                "user_id": ticket.user_id,
                "note_text": message.message_text,
            },
        )
        service.db.commit()
    except Exception:
        service.db.rollback()
    _publish_hr_realtime("hr_ticket_internal_note", {"ticket_id": str(ticket.id)})
    return msg


@router.post("/{ticket_id}/close", response_model=TicketResponse)
def close_ticket(
    ticket_id: UUID,
    payload: TicketCloseRequest,
    current_user: User = Depends(get_current_user),
    service: TicketService = Depends(get_ticket_service),
):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(status_code=403, detail="Only HR/Admin can close tickets")

    existing = service.get_ticket(ticket_id, current_user.id, is_hr=True)
    previous_status = (
        existing.status.value if existing and hasattr(existing.status, "value") else str(existing.status) if existing else None
    )
    ticket = service.update_ticket(
        ticket_id=ticket_id,
        user_id=current_user.id,
        is_hr=True,
        status=TicketStatus.resolved,
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    service.add_message(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message_text=(payload.resolution_note or "Resolved by HR"),
        is_internal=True,
    )
    _log_ticket_action(service.db, ticket.id, current_user.id, "close", payload.resolution_note or "Resolved by HR")
    _notify_hr(
        service.db,
        ticket.id,
        current_user.id,
        title="Ticket closed",
        body=payload.resolution_note or "Resolved by HR",
        notification_type="ticket_closed",
        severity="info",
    )
    try:
        AutomationRulesService(service.db).apply_ticket_updated_rules(
            ticket,
            previous_status=previous_status,
            actor_id=current_user.id,
        )
        AutomationRulesService(service.db).apply_event_rules(
            event_type="ticket_closed",
            context={
                "ticket": ticket,
                "actor_id": current_user.id,
                "user_id": ticket.user_id,
                "resolution_note": payload.resolution_note or "Resolved by HR",
            },
        )
        service.db.commit()
    except Exception:
        service.db.rollback()
    _publish_hr_realtime("hr_ticket_closed", {"ticket_id": str(ticket.id)})
    try:
        preview = (ticket.query or "")[:120]
        notify_ticket_update(
            service.db,
            user_id=ticket.user_id,
            kind="closed",
            summary=preview,
            detail=(payload.resolution_note or "")[:500],
        )
    except Exception:
        pass
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
    existing = service.get_ticket(ticket_id, current_user.id, is_hr)
    previous_status = (
        existing.status.value if existing and hasattr(existing.status, "value") else str(existing.status) if existing else None
    )
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
    try:
        AutomationRulesService(service.db).apply_ticket_updated_rules(
            ticket,
            previous_status=previous_status,
            actor_id=current_user.id,
        )
    except Exception:
        service.db.rollback()
    _publish_hr_realtime(
        "hr_ticket_updated",
        {"ticket_id": str(ticket.id), "status": str(ticket.status.value if hasattr(ticket.status, "value") else ticket.status)},
    )
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


@router.get("/{ticket_id}/actions", response_model=List[TicketActionLogResponse])
def list_ticket_actions(
    ticket_id: UUID,
    current_user=Depends(require_roles(["hr", "admin"])),
    service: TicketService = Depends(get_ticket_service),
):
    ticket = service.get_ticket(ticket_id, current_user.id, True)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return (
        service.db.query(TicketActionLog)
        .filter(TicketActionLog.ticket_id == ticket_id)
        .order_by(TicketActionLog.created_at.desc())
        .all()
    )


@router.get("/{ticket_id}/related", response_model=List[TicketResponse])
def list_related_tickets(
    ticket_id: UUID,
    current_user=Depends(require_roles(["hr", "admin"])),
    service: TicketService = Depends(get_ticket_service),
):
    ticket = service.get_ticket(ticket_id, current_user.id, True)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    related = service.list_related_tickets(ticket=ticket, limit=8)
    return [enrich_ticket_response(row, service) for row in related]


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
    if is_hr:
        _log_ticket_action(service.db, ticket.id, current_user.id, "employee_visible_reply", message.message_text)
        _notify_hr(
            service.db,
            ticket.id,
            current_user.id,
            title="HR reply posted",
            body=message.message_text,
            notification_type="ticket_reply",
            severity="info",
        )
        try:
            AutomationRulesService(service.db).apply_event_rules(
                event_type="ticket_reply_posted",
                context={
                    "ticket": ticket,
                    "actor_id": current_user.id,
                    "user_id": ticket.user_id,
                    "message_text": message.message_text,
                },
            )
            service.db.commit()
        except Exception:
            service.db.rollback()
        _publish_hr_realtime("hr_ticket_reply_posted", {"ticket_id": str(ticket.id)})
        try:
            preview = (ticket.query or "")[:100]
            notify_ticket_update(
                service.db,
                user_id=ticket.user_id,
                kind="hr_reply",
                summary=preview,
                detail=(message.message_text or "")[:500],
            )
        except Exception:
            pass
    return msg


@router.post("/sla-scan/trigger")
def trigger_sla_scan(_hr=Depends(require_roles(["hr", "admin"]))):
    """Run the SLA breach scan on demand.

    Role-gated: this is an unbounded DB job that also reports how many tickets
    have breached, so leaving it open let anyone who could reach the API both
    load the database at will and read internal backlog state. Every other
    route in this module was already guarded; this one was missed.
    """
    from ...services.scheduler import check_and_escalate_sla_breached_tickets
    result = check_and_escalate_sla_breached_tickets()
    return result


@router.get("/{ticket_id}/ai-summary")
def get_ticket_ai_summary(
    ticket_id: UUID,
    refresh: bool = False,
    current_user=Depends(require_roles(["hr", "admin"])),
    service: TicketService = Depends(get_ticket_service),
):
    """LLM-generated summary of the ticket and recent thread.

    Result is cached in Redis keyed on ``ticket_id:updated_at``; passing
    ``refresh=true`` forces regeneration. Falls back to a deterministic
    template summary if the LLM call fails or Azure OpenAI is unconfigured.
    """
    import json
    from ...cache import get_cached, set_cached
    from ...ai_client import get_ai_client
    from ...config import settings

    ticket = service.get_ticket(ticket_id, current_user.id, True)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    updated_marker = (ticket.updated_at or ticket.created_at or datetime.utcnow()).isoformat()
    cache_key = f"ticket_ai_summary:{ticket_id}:{updated_marker}"
    if not refresh:
        cached = get_cached(cache_key)
        if cached:
            return cached

    messages = service.list_messages(ticket_id, user_id=current_user.id, is_hr=True) or []
    thread_lines: List[str] = []
    for m in messages[-20:]:
        role = "HR" if getattr(m, "sender_id", None) else "Employee"
        is_internal = bool(getattr(m, "is_internal", False))
        if is_internal:
            role = "HR (internal note)"
        text = (getattr(m, "message_text", "") or "").strip().replace("\n", " ")
        if text:
            thread_lines.append(f"- {role}: {text[:400]}")

    body = ticket.query or ""
    prompt_user = (
        f"Ticket category: {ticket.category}\n"
        f"Priority: {ticket.priority}\n"
        f"Status: {ticket.status}\n"
        f"Opening query: {body[:600]}\n\n"
        f"Recent thread (most recent last):\n" + ("\n".join(thread_lines) if thread_lines else "(no replies yet)")
    )

    use_mock = not settings.AZURE_OPENAI_API_KEY or settings.AZURE_OPENAI_API_KEY == "mock-key"

    summary_text: Optional[str] = None
    if not use_mock:
        try:
            client = get_ai_client(use_mock=False)
            response = client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an HR operations assistant. Write a concise 2-3 sentence summary "
                            "of an HR ticket for an HR business partner. Focus on what the employee "
                            "needs and the single most useful next action. Plain text, no markdown."
                        ),
                    },
                    {"role": "user", "content": prompt_user},
                ],
                temperature=0.2,
                max_tokens=200,
            )
            summary_text = (
                (response.get("choices") or [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
        except Exception:
            logger.warning("Ticket AI summary failed; falling back to template", exc_info=True)

    if not summary_text:
        summary_text = (
            f"{ticket.category.title()} ticket at {ticket.priority} priority — "
            f"{body[:160].rstrip()}. "
            f"{'Awaiting first HR response.' if not thread_lines else 'See thread for the latest context.'}"
        )

    payload = {
        "ticket_id": str(ticket_id),
        "summary": summary_text,
        "generated_at": datetime.utcnow().isoformat(),
        "model": "azure-openai" if not use_mock and summary_text else "template",
        "message_count": len(messages),
    }
    set_cached(cache_key, payload, ttl=3600)
    return payload


@router.get("/{ticket_id}/sentiment-history")
def get_ticket_sentiment_history(
    ticket_id: UUID,
    current_user=Depends(require_roles(["hr", "admin"])),
    service: TicketService = Depends(get_ticket_service),
):
    """Sentiment trajectory of the ticket creator since the ticket was opened.

    Returns daily averages of SentimentLog.score for ``ticket.user_id`` since
    ``ticket.created_at``. Empty list if no logs exist.
    """
    from sqlalchemy import func
    from ...models.sentiment_log import SentimentLog

    ticket = service.get_ticket(ticket_id, current_user.id, True)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    since = ticket.created_at or (datetime.utcnow() - timedelta(days=14))
    day = func.date(SentimentLog.created_at).label("day")
    rows = (
        service.db.query(day, func.avg(SentimentLog.score).label("avg_score"), func.count(SentimentLog.id).label("n"))
        .filter(SentimentLog.employee_id == ticket.user_id, SentimentLog.created_at >= since)
        .group_by(day)
        .order_by(day)
        .all()
    )

    return {
        "ticket_id": str(ticket_id),
        "user_id": str(ticket.user_id),
        "since": since.isoformat(),
        "points": [
            {
                "date": str(r.day),
                "score": round(float(r.avg_score), 1) if r.avg_score is not None else None,
                "sample_size": int(r.n),
            }
            for r in rows
        ],
    }
