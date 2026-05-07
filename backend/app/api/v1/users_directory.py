"""Directory: users for HR and profile lookup by id."""
from __future__ import annotations

import os
from datetime import date
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ...auth import get_current_user, require_roles
from ...database import get_db
from ...models.department import Department
from ...models.survey import Survey, SurveyResponse
from ...models.ticket import Ticket
from ...models.user import User, UserRole, UserStatus
from ...models.leave_request import LeaveRequest, LeaveStatus as LeaveRowStatus

router = APIRouter(prefix="/users", tags=["users"])


class UserListItem(BaseModel):
    id: str
    email: str
    name: str
    role: str
    employee_id: Optional[str] = None
    designation: Optional[str] = None
    department: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class TimelineItem(BaseModel):
    date: str
    text: str
    tone: str


class UserDetailResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    employee_id: Optional[str] = None
    designation: Optional[str] = None
    department: str
    location: str = "—"
    joined_at: Optional[str] = None
    manager_id: Optional[str] = None
    manager_name: Optional[str] = None
    sentiment: str = "neutral"
    risk_score: int = 0
    leave_balance: int = 0
    annual_leave_days: int = 25
    used_leave_days_ytd: int = 0

    model_config = ConfigDict(from_attributes=True)


def _dept_map(db: Session) -> dict[str, str]:
    return {str(d.id): d.name for d in db.query(Department).all()}


def _can_view(target: User, viewer: User) -> bool:
    if viewer.role in (UserRole.hr, UserRole.admin):
        return True
    return str(viewer.id) == str(target.id)


def _leave_balance_for_user(db: Session, user_id) -> Tuple[int, int, int]:
    annual = int(os.getenv("ANNUAL_LEAVE_DAYS", "25"))
    year_start = date(date.today().year, 1, 1)
    year_end = date(date.today().year, 12, 31)
    rows = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.user_id == user_id,
            LeaveRequest.status == LeaveRowStatus.approved,
            LeaveRequest.start_date <= year_end,
            LeaveRequest.end_date >= year_start,
        )
        .all()
    )
    used = 0
    for r in rows:
        s = max(r.start_date, year_start)
        e = min(r.end_date, year_end)
        if e >= s:
            used += (e - s).days + 1
    remaining = max(0, annual - used)
    return annual, used, remaining


@router.get("", response_model=List[UserListItem])
def list_users(
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    dept = _dept_map(db)
    users = db.query(User).filter(User.status == UserStatus.active).order_by(User.name).all()
    out: List[UserListItem] = []
    for u in users:
        dname = dept.get(str(u.department_id), "General") if u.department_id else "General"
        out.append(
            UserListItem(
                id=str(u.id),
                email=u.email,
                name=u.name,
                role=u.role.value if hasattr(u.role, "value") else str(u.role),
                employee_id=u.employee_id,
                designation=u.designation,
                department=dname,
                status=u.status.value if hasattr(u.status, "value") else str(u.status),
            )
        )
    return out


@router.get("/{user_id}/timeline", response_model=List[TimelineItem])
def get_user_timeline(
    user_id: UUID,
    limit: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not _can_view(u, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    limit = max(1, min(limit, 40))
    items: List[TimelineItem] = []

    for t in (
        db.query(Ticket)
        .filter(Ticket.user_id == user_id)
        .order_by(Ticket.created_at.desc())
        .limit(8)
        .all()
    ):
        items.append(
            TimelineItem(
                date=t.created_at.date().isoformat() if t.created_at else "",
                text=f"Ticket: {(t.query or '')[:80]}",
                tone="neutral",
            )
        )

    for r in (
        db.query(SurveyResponse)
        .filter(SurveyResponse.user_id == user_id)
        .order_by(SurveyResponse.created_at.desc())
        .limit(5)
        .all()
    ):
        surv = db.query(Survey).filter(Survey.id == r.survey_id).first()
        title = surv.title if surv else "Survey"
        items.append(
            TimelineItem(
                date=r.created_at.date().isoformat() if r.created_at else "",
                text=f"Survey response: {title}",
                tone="positive",
            )
        )

    for lv in (
        db.query(LeaveRequest)
        .filter(LeaveRequest.user_id == user_id)
        .order_by(LeaveRequest.created_at.desc())
        .limit(8)
        .all()
    ):
        st = lv.status.value if hasattr(lv.status, "value") else str(lv.status)
        lt = lv.leave_type.value if hasattr(lv.leave_type, "value") else str(lv.leave_type)
        lt_label = str(lt).replace("_", " ")
        if st == "approved":
            tone = "positive"
        elif st == "rejected":
            tone = "danger"
        else:
            tone = "neutral"
        items.append(
            TimelineItem(
                date=lv.created_at.date().isoformat() if lv.created_at else "",
                text=f"Leave ({st}): {lv.start_date} → {lv.end_date} ({lt_label})",
                tone=tone,
            )
        )

    items.sort(key=lambda x: x.date, reverse=True)
    return items[:limit]


@router.get("/{user_id}", response_model=UserDetailResponse)
def get_user_detail(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not _can_view(u, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this profile")

    dept = _dept_map(db)
    dname = dept.get(str(u.department_id), "General") if u.department_id else "General"
    mgr_name = None
    if u.manager_id:
        m = db.query(User).filter(User.id == u.manager_id).first()
        if m:
            mgr_name = m.name

    from ...services.dashboard_analytics import employee_insights_for_hr

    risk = 0
    sentiment_label = "neutral"
    try:
        rows = employee_insights_for_hr(db, limit=200)
        match = next((r for r in rows if r.get("id") == str(u.id) or r.get("employee_id") == u.employee_id), None)
        if match:
            risk = int(match.get("risk_score") or 0)
            s = int(match.get("sentiment_score") or 50)
            if s >= 75:
                sentiment_label = "positive"
            elif s >= 55:
                sentiment_label = "neutral"
            elif s >= 35:
                sentiment_label = "watch"
            else:
                sentiment_label = "at_risk"
    except Exception:
        pass

    annual, used, remaining = _leave_balance_for_user(db, u.id)

    return UserDetailResponse(
        id=str(u.id),
        email=u.email,
        name=u.name,
        role=u.role.value if hasattr(u.role, "value") else str(u.role),
        employee_id=u.employee_id,
        designation=u.designation,
        department=dname,
        location="—",
        joined_at=u.created_at.date().isoformat() if u.created_at else None,
        manager_id=str(u.manager_id) if u.manager_id else None,
        manager_name=mgr_name,
        sentiment=sentiment_label,
        risk_score=risk,
        leave_balance=remaining,
        annual_leave_days=annual,
        used_leave_days_ytd=used,
    )
