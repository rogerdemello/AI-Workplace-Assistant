from fastapi import APIRouter, Depends, HTTPException, status
import asyncio
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ...database import get_db
from ...core.time import utcnow_naive
from ...schemas.leave import (
    LeaveCreate,
    LeaveApproveReject,
    LeaveResponse,
    LeaveStatus,
    LeaveType,
)
from ...auth import get_current_user
from ...models.user import User, UserRole
from ...models.leave_request import LeaveRequest, LeaveStatus as ModelLeaveStatus
from ...services.automation_rules import AutomationRulesService
from ...services.realtime_bus import realtime_bus
from ...services.v2.whatsapp_notify import notify_leave_decision

router = APIRouter(prefix="/leave", tags=["leave"])


def _publish_hr_realtime(event_type: str, payload: dict) -> None:
    try:
        asyncio.run(realtime_bus.publish(event_type, payload))
    except Exception:
        pass


def _can_review_leave(db: Session, actor: User, leave: LeaveRequest) -> bool:
    if actor.role in (UserRole.hr, UserRole.admin):
        return True
    subordinate = db.query(User).filter(User.id == leave.user_id).first()
    return bool(subordinate and subordinate.manager_id == actor.id)


def _is_line_manager(db: Session, user: User) -> bool:
    if user.role in (UserRole.hr, UserRole.admin):
        return True
    n = db.query(User).filter(User.manager_id == user.id).count()
    return n > 0


def _list_leaves_for_user(db: Session, current_user: User, status_filter: Optional[ModelLeaveStatus] = None) -> List[LeaveRequest]:
    q = db.query(LeaveRequest)
    if status_filter:
        q = q.filter(LeaveRequest.status == status_filter)

    if current_user.role in (UserRole.hr, UserRole.admin):
        return q.order_by(LeaveRequest.created_at.desc()).all()

    report_ids = [r[0] for r in db.query(User.id).filter(User.manager_id == current_user.id).all()]
    if report_ids:
        # Include the manager's own requests — otherwise anyone with a direct
        # report loses sight of their own leave entirely.
        return (
            q.filter(LeaveRequest.user_id.in_([current_user.id, *report_ids]))
            .order_by(LeaveRequest.created_at.desc())
            .all()
        )

    return q.filter(LeaveRequest.user_id == current_user.id).order_by(LeaveRequest.created_at.desc()).all()


def _get_leave_if_visible(db: Session, leave_id: UUID, current_user: User) -> Optional[LeaveRequest]:
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        return None
    if leave.user_id == current_user.id:
        return leave
    if _can_review_leave(db, current_user, leave):
        return leave
    return None


def _enrich_leave(db: Session, leave: LeaveRequest) -> LeaveResponse:
    u = db.query(User).filter(User.id == leave.user_id).first()
    base = LeaveResponse.model_validate(leave)
    return base.model_copy(update={"employee_name": u.name if u else None})


def create_leave_request(
    db: Session,
    user_id: UUID,
    start_date,
    end_date,
    leave_type,
    reason: Optional[str] = None,
):
    leave = LeaveRequest(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        leave_type=leave_type,
        reason=reason,
        status=ModelLeaveStatus.pending,
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


@router.post("", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
def create_leave(
    leave_data: LeaveCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    overlapping = db.query(LeaveRequest).filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status.in_([ModelLeaveStatus.pending, ModelLeaveStatus.approved]),
        LeaveRequest.start_date <= leave_data.end_date,
        LeaveRequest.end_date >= leave_data.start_date,
    ).first()

    leave = create_leave_request(
        db=db,
        user_id=current_user.id,
        start_date=leave_data.start_date,
        end_date=leave_data.end_date,
        leave_type=leave_data.leave_type,
        reason=leave_data.reason,
    )

    from fastapi.responses import JSONResponse

    response_data = _enrich_leave(db, leave).model_dump(mode="json")
    try:
        AutomationRulesService(db).apply_event_rules(
            event_type="leave_requested",
            context={
                "leave": leave,
                "actor_id": current_user.id,
                "user_id": current_user.id,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
    response = JSONResponse(content=response_data, status_code=status.HTTP_201_CREATED)
    if overlapping:
        response.headers["X-Leave-Overlap-Warning"] = (
            f"You already have leave from {overlapping.start_date} "
            f"to {overlapping.end_date}. Do you still want to proceed?"
        )
    _publish_hr_realtime("hr_leave_requested", {"leave_id": str(leave.id), "user_id": str(current_user.id)})
    return response


@router.get("", response_model=List[LeaveResponse])
def list_leave(
    status_filter: Optional[ModelLeaveStatus] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    leaves = _list_leaves_for_user(db, current_user, status_filter)
    return [_enrich_leave(db, lv) for lv in leaves]


@router.get("/{leave_id}", response_model=LeaveResponse)
def get_leave(
    leave_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    leave = _get_leave_if_visible(db, leave_id, current_user)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return _enrich_leave(db, leave)


@router.patch("/{leave_id}/approve", response_model=LeaveResponse)
def approve_leave(
    leave_id: UUID,
    data: LeaveApproveReject = LeaveApproveReject(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_line_manager(db, current_user) and current_user.role not in (UserRole.hr, UserRole.admin):
        raise HTTPException(status_code=403, detail="Only managers or HR can approve leave requests")

    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if not _can_review_leave(db, current_user, leave):
        raise HTTPException(status_code=403, detail="You cannot approve this leave request")

    if leave.status != ModelLeaveStatus.pending:
        raise HTTPException(status_code=400, detail="Leave request is not pending")

    leave.status = ModelLeaveStatus.approved
    leave.manager_id = current_user.id
    leave.reviewed_at = utcnow_naive()
    leave.review_comment = data.review_comment

    db.commit()
    db.refresh(leave)
    try:
        AutomationRulesService(db).apply_leave_reviewed_rules(leave, actor_id=current_user.id)
    except Exception:
        db.rollback()
    _publish_hr_realtime("hr_leave_approved", {"leave_id": str(leave.id), "user_id": str(leave.user_id)})
    try:
        summary = f"{leave.start_date} – {leave.end_date}"
        if leave.review_comment:
            summary += f". Note: {leave.review_comment}"
        notify_leave_decision(db, user_id=leave.user_id, action="approved", summary=summary)
    except Exception:
        pass
    return _enrich_leave(db, leave)


@router.patch("/{leave_id}/reject", response_model=LeaveResponse)
def reject_leave(
    leave_id: UUID,
    data: LeaveApproveReject = LeaveApproveReject(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_line_manager(db, current_user) and current_user.role not in (UserRole.hr, UserRole.admin):
        raise HTTPException(status_code=403, detail="Only managers or HR can reject leave requests")

    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if not _can_review_leave(db, current_user, leave):
        raise HTTPException(status_code=403, detail="You cannot reject this leave request")

    if leave.status != ModelLeaveStatus.pending:
        raise HTTPException(status_code=400, detail="Leave request is not pending")

    leave.status = ModelLeaveStatus.rejected
    leave.manager_id = current_user.id
    leave.reviewed_at = utcnow_naive()
    leave.review_comment = data.review_comment

    db.commit()
    db.refresh(leave)
    try:
        AutomationRulesService(db).apply_leave_reviewed_rules(leave, actor_id=current_user.id)
    except Exception:
        db.rollback()
    _publish_hr_realtime("hr_leave_rejected", {"leave_id": str(leave.id), "user_id": str(leave.user_id)})
    try:
        summary = f"{leave.start_date} – {leave.end_date}"
        if leave.review_comment:
            summary += f". Reason: {leave.review_comment}"
        notify_leave_decision(db, user_id=leave.user_id, action="rejected", summary=summary)
    except Exception:
        pass
    return _enrich_leave(db, leave)


@router.patch("/{leave_id}/cancel", response_model=LeaveResponse)
def cancel_leave(
    leave_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    leave = _get_leave_if_visible(db, leave_id, current_user)
    if not leave or leave.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if leave.status != ModelLeaveStatus.pending:
        raise HTTPException(status_code=400, detail="Only pending leave requests can be cancelled")

    leave.status = ModelLeaveStatus.rejected
    leave.review_comment = "Cancelled by employee"
    db.commit()
    db.refresh(leave)
    try:
        AutomationRulesService(db).apply_event_rules(
            event_type="leave_cancelled",
            context={
                "leave": leave,
                "actor_id": current_user.id,
                "user_id": current_user.id,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
    _publish_hr_realtime("hr_leave_cancelled", {"leave_id": str(leave.id), "user_id": str(current_user.id)})
    try:
        summary = f"{leave.start_date} – {leave.end_date}"
        notify_leave_decision(db, user_id=current_user.id, action="cancelled", summary=summary)
    except Exception:
        pass
    return _enrich_leave(db, leave)
