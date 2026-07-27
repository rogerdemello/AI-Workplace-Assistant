"""Employee requests raised through chat — appointments, expenses, shift changes, documents.

Employees see only their own rows; HR and admins see everything and action it.
Managers see their direct reports so shift changes can be approved in line.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
import asyncio
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_ as sa_and, func, or_ as sa_or
from typing import List, Optional
from uuid import UUID

from ...database import get_db
from ...core.time import utcnow_naive
from ...auth import get_current_user
from ...models.user import User, UserRole
from ...models.employee_request import (
    EmployeeRequest,
    RequestStatus as ModelRequestStatus,
    RequestType as ModelRequestType,
    TERMINAL_STATUSES,
)
from ...schemas.employee_request import (
    EmployeeRequestCreate,
    EmployeeRequestDecision,
    EmployeeRequestResponse,
    EmployeeRequestSummary,
    RequestStatus,
    RequestType,
)
from ...services.realtime_bus import realtime_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/requests", tags=["requests"])


def _publish_hr_realtime(event_type: str, payload: dict) -> None:
    try:
        asyncio.run(realtime_bus.publish(event_type, payload))
    except Exception:
        pass


#: Request types a line manager may see and action for their direct reports.
#:
#: Deliberately excludes appointments and documents. An appointment's title
#: carries the employee's own words ("1:1 with HR — my manager keeps..."), and a
#: relieving or experience letter request signals they are leaving. Exposing
#: either to the manager they may be escaping defeats the point of a
#: confidential channel, so those stay with HR regardless of reporting line.
MANAGER_REVIEWABLE_TYPES = (ModelRequestType.shift_change, ModelRequestType.expense)


def _is_reviewer(user: User) -> bool:
    return user.role in (UserRole.hr, UserRole.admin)


def _report_ids(db: Session, user: User) -> List[UUID]:
    return [row[0] for row in db.query(User.id).filter(User.manager_id == user.id).all()]


def _can_review(db: Session, actor: User, request: EmployeeRequest) -> bool:
    if _is_reviewer(actor):
        return True
    if request.request_type not in MANAGER_REVIEWABLE_TYPES:
        return False
    employee = db.query(User).filter(User.id == request.user_id).first()
    return bool(employee and employee.manager_id == actor.id)


def _visible_query(db: Session, current_user: User):
    query = db.query(EmployeeRequest)
    if _is_reviewer(current_user):
        return query

    own = EmployeeRequest.user_id == current_user.id
    reports = _report_ids(db, current_user)
    if not reports:
        return query.filter(own)

    # Own requests in full; reports' only where the manager has a role to play.
    return query.filter(
        sa_or(
            own,
            sa_and(
                EmployeeRequest.user_id.in_(reports),
                EmployeeRequest.request_type.in_(MANAGER_REVIEWABLE_TYPES),
            ),
        )
    )


def _enrich(db: Session, request: EmployeeRequest) -> EmployeeRequestResponse:
    employee = db.query(User).filter(User.id == request.user_id).first()
    base = EmployeeRequestResponse.model_validate(request)
    return base.model_copy(update={"employee_name": employee.name if employee else None})


@router.post("", response_model=EmployeeRequestResponse, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: EmployeeRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = EmployeeRequest(
        user_id=current_user.id,
        request_type=ModelRequestType(payload.request_type.value),
        status=ModelRequestStatus.pending,
        title=payload.title,
        details=payload.details or {},
        scheduled_at=payload.scheduled_at,
        start_date=payload.start_date,
        end_date=payload.end_date,
        amount=payload.amount,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    _publish_hr_realtime(
        "hr_request_created",
        {
            "request_id": str(request.id),
            "user_id": str(current_user.id),
            "request_type": request.request_type.value,
        },
    )
    return _enrich(db, request)


@router.get("", response_model=List[EmployeeRequestResponse])
def list_requests(
    request_type: Optional[RequestType] = None,
    request_status: Optional[RequestStatus] = Query(default=None, alias="status"),
    mine_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = _visible_query(db, current_user)
    if mine_only:
        query = query.filter(EmployeeRequest.user_id == current_user.id)
    if request_type:
        query = query.filter(EmployeeRequest.request_type == ModelRequestType(request_type.value))
    if request_status:
        query = query.filter(EmployeeRequest.status == ModelRequestStatus(request_status.value))

    rows = query.order_by(EmployeeRequest.created_at.desc()).limit(limit).all()
    return [_enrich(db, row) for row in rows]


@router.get("/summary", response_model=EmployeeRequestSummary)
def request_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Status and type counts for the HR dashboard tiles."""
    base = _visible_query(db, current_user).subquery()

    status_counts = dict(
        db.query(base.c.status, func.count()).group_by(base.c.status).all()
    )
    type_counts = dict(
        db.query(base.c.request_type, func.count()).group_by(base.c.request_type).all()
    )

    def _key(value) -> str:
        return value.value if hasattr(value, "value") else str(value)

    summary = EmployeeRequestSummary(
        by_type={_key(k): int(v) for k, v in type_counts.items()},
    )
    for raw_status, count in status_counts.items():
        field = _key(raw_status)
        if hasattr(summary, field):
            setattr(summary, field, int(count))
    return summary


@router.get("/{request_id}", response_model=EmployeeRequestResponse)
def get_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = _visible_query(db, current_user).filter(EmployeeRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    return _enrich(db, request)


#: What Mark tells the employee once HR has actioned their request.
_DECISION_LINES = {
    ModelRequestStatus.approved: "Good news — HR approved your {label}.",
    ModelRequestStatus.rejected: "HR reviewed your {label} and couldn't approve it this time.",
    ModelRequestStatus.completed: "Your {label} is done and dusted.",
    ModelRequestStatus.scheduled: "Your {label} is confirmed for {when}.",
}


def _notify_employee(db: Session, request: EmployeeRequest, new_status: ModelRequestStatus) -> None:
    """Close the loop in chat so the employee isn't left guessing.

    Best-effort: a notification failure must never roll back HR's decision.
    """
    template = _DECISION_LINES.get(new_status)
    if not template:
        return

    when = ""
    if request.scheduled_at:
        when = request.scheduled_at.strftime("%d %b at %H:%M")

    message = template.format(label=request.title.lower(), when=when)
    if request.hr_note:
        message = f"{message} Note from HR: {request.hr_note}"

    try:
        from ...services.mark_proactive import get_mark_proactive_service

        get_mark_proactive_service(db).notify_user(
            request.user_id,
            message,
            nudge_type=f"request_{new_status.value}",
            action_url="/requests",
        )
    except Exception:
        logger.warning(
            "Failed to notify employee about request %s", request.id, exc_info=True
        )


def _apply_decision(
    db: Session,
    request: EmployeeRequest,
    actor: User,
    new_status: ModelRequestStatus,
    note: Optional[str],
) -> None:
    request.status = new_status
    request.handled_by = actor.id
    request.handled_at = utcnow_naive()
    if note:
        request.hr_note = note
    _notify_employee(db, request, new_status)


def _load_for_review(db: Session, request_id: UUID, actor: User) -> EmployeeRequest:
    request = db.query(EmployeeRequest).filter(EmployeeRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    if not _can_review(db, actor, request):
        raise HTTPException(status_code=403, detail="You cannot action this request")
    if request.status in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Request is already {request.status.value}"
        )
    return request


@router.patch("/{request_id}/approve", response_model=EmployeeRequestResponse)
def approve_request(
    request_id: UUID,
    data: EmployeeRequestDecision = EmployeeRequestDecision(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = _load_for_review(db, request_id, current_user)
    _apply_decision(db, request, current_user, ModelRequestStatus.approved, data.hr_note)
    db.commit()
    db.refresh(request)
    _publish_hr_realtime(
        "hr_request_approved",
        {"request_id": str(request.id), "user_id": str(request.user_id)},
    )
    return _enrich(db, request)


@router.patch("/{request_id}/reject", response_model=EmployeeRequestResponse)
def reject_request(
    request_id: UUID,
    data: EmployeeRequestDecision = EmployeeRequestDecision(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = _load_for_review(db, request_id, current_user)
    _apply_decision(db, request, current_user, ModelRequestStatus.rejected, data.hr_note)
    db.commit()
    db.refresh(request)
    _publish_hr_realtime(
        "hr_request_rejected",
        {"request_id": str(request.id), "user_id": str(request.user_id)},
    )
    return _enrich(db, request)


@router.patch("/{request_id}/schedule", response_model=EmployeeRequestResponse)
def schedule_request(
    request_id: UUID,
    data: EmployeeRequestDecision,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm (or move) an appointment slot."""
    request = _load_for_review(db, request_id, current_user)
    if request.request_type != ModelRequestType.appointment:
        raise HTTPException(status_code=400, detail="Only appointments can be scheduled")
    if not data.scheduled_at:
        raise HTTPException(status_code=400, detail="scheduled_at is required")

    request.scheduled_at = data.scheduled_at
    _apply_decision(db, request, current_user, ModelRequestStatus.scheduled, data.hr_note)
    db.commit()
    db.refresh(request)
    _publish_hr_realtime(
        "hr_request_scheduled",
        {
            "request_id": str(request.id),
            "user_id": str(request.user_id),
            "scheduled_at": request.scheduled_at.isoformat() if request.scheduled_at else None,
        },
    )
    return _enrich(db, request)


@router.patch("/{request_id}/complete", response_model=EmployeeRequestResponse)
def complete_request(
    request_id: UUID,
    data: EmployeeRequestDecision = EmployeeRequestDecision(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = _load_for_review(db, request_id, current_user)
    _apply_decision(db, request, current_user, ModelRequestStatus.completed, data.hr_note)
    db.commit()
    db.refresh(request)
    return _enrich(db, request)


@router.patch("/{request_id}/cancel", response_model=EmployeeRequestResponse)
def cancel_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Employees withdraw their own request; HR should reject rather than cancel."""
    request = db.query(EmployeeRequest).filter(EmployeeRequest.id == request_id).first()
    if not request or request.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Request not found")
    if request.status in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Request is already {request.status.value}"
        )

    request.status = ModelRequestStatus.cancelled
    request.handled_at = utcnow_naive()
    db.commit()
    db.refresh(request)
    _publish_hr_realtime(
        "hr_request_cancelled",
        {"request_id": str(request.id), "user_id": str(current_user.id)},
    )
    return _enrich(db, request)
