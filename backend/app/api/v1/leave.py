from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ...database import get_db
from ...core.time import utcnow_naive
from ...schemas.leave import (
    LeaveCreate, LeaveUpdate, LeaveResponse, 
    LeaveApproveReject, LeaveStatus, LeaveType
)
from ...auth import get_current_user
from ...models.user import User
from ...models.leave_request import LeaveRequest, LeaveStatus as ModelLeaveStatus

router = APIRouter(prefix="/leave", tags=["leave"])


def get_leave_requests(
    db: Session = Depends(get_db),
    user_id: Optional[UUID] = None,
    status_filter: Optional[ModelLeaveStatus] = None,
    manager_id: Optional[UUID] = None
):
    query = db.query(LeaveRequest)
    
    if user_id:
        query = query.filter(LeaveRequest.user_id == user_id)
    if status_filter:
        query = query.filter(LeaveRequest.status == status_filter)
    if manager_id:
        query = query.filter(LeaveRequest.manager_id == manager_id)
    
    return query.order_by(LeaveRequest.created_at.desc()).all()


def get_leave_request(db: Session, leave_id: UUID, user_id: UUID, is_manager: bool = False):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        return None
    if is_manager:
        return leave
    if leave.user_id != user_id:
        return None
    return leave


def create_leave_request(
    db: Session,
    user_id: UUID,
    start_date,
    end_date,
    leave_type,
    reason: Optional[str] = None
):
    from datetime import date
    
    leave = LeaveRequest(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        leave_type=leave_type,
        reason=reason,
        status=ModelLeaveStatus.pending
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


@router.post("", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
def create_leave(
    leave_data: LeaveCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
        reason=leave_data.reason
    )

    from fastapi.responses import JSONResponse
    response_data = LeaveResponse.model_validate(leave).model_dump(mode="json")
    response = JSONResponse(content=response_data, status_code=status.HTTP_201_CREATED)
    if overlapping:
        response.headers["X-Leave-Overlap-Warning"] = (
            f"You already have leave from {overlapping.start_date} "
            f"to {overlapping.end_date}. Do you still want to proceed?"
        )
    return response


@router.get("", response_model=List[LeaveResponse])
def list_leave(
    status_filter: Optional[ModelLeaveStatus] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    is_manager = current_user.role in ["hr", "admin", "manager"]
    
    if is_manager:
        leaves = get_leave_requests(
            db=db,
            status_filter=status_filter,
            manager_id=current_user.id
        )
        if not leaves:
            leaves = get_leave_requests(db=db, status_filter=status_filter)
    else:
        leaves = get_leave_requests(
            db=db,
            user_id=current_user.id,
            status_filter=status_filter
        )
    
    return leaves


@router.get("/{leave_id}", response_model=LeaveResponse)
def get_leave(
    leave_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    is_manager = current_user.role in ["hr", "admin", "manager"]
    leave = get_leave_request(db, leave_id, current_user.id, is_manager)
    
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return leave


@router.patch("/{leave_id}/approve", response_model=LeaveResponse)
def approve_leave(
    leave_id: UUID,
    data: LeaveApproveReject = LeaveApproveReject(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from datetime import datetime
    
    if current_user.role not in ["hr", "admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only managers can approve leave requests")
    
    leave = get_leave_request(db, leave_id, current_user.id, is_manager=True)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    if leave.status != ModelLeaveStatus.pending:
        raise HTTPException(status_code=400, detail="Leave request is not pending")
    
    leave.status = ModelLeaveStatus.approved
    leave.manager_id = current_user.id
    leave.reviewed_at = utcnow_naive()
    leave.review_comment = data.review_comment
    
    db.commit()
    db.refresh(leave)
    return leave


@router.patch("/{leave_id}/reject", response_model=LeaveResponse)
def reject_leave(
    leave_id: UUID,
    data: LeaveApproveReject = LeaveApproveReject(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from datetime import datetime
    
    if current_user.role not in ["hr", "admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only managers can reject leave requests")
    
    leave = get_leave_request(db, leave_id, current_user.id, is_manager=True)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    if leave.status != ModelLeaveStatus.pending:
        raise HTTPException(status_code=400, detail="Leave request is not pending")
    
    leave.status = ModelLeaveStatus.rejected
    leave.manager_id = current_user.id
    leave.reviewed_at = utcnow_naive()
    leave.review_comment = data.review_comment
    
    db.commit()
    db.refresh(leave)
    return leave


@router.patch("/{leave_id}/cancel", response_model=LeaveResponse)
def cancel_leave(
    leave_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    leave = get_leave_request(db, leave_id, current_user.id, is_manager=False)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if leave.status != ModelLeaveStatus.pending:
        raise HTTPException(status_code=400, detail="Only pending leave requests can be cancelled")

    # Model currently supports pending/approved/rejected only.
    # Employee cancellation transitions pending requests to rejected.
    leave.status = ModelLeaveStatus.rejected
    leave.review_comment = "Cancelled by employee"
    db.commit()
    db.refresh(leave)
    return leave