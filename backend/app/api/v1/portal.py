"""Employee / manager self-service endpoints (authenticated, not HR-only)."""
from __future__ import annotations

import os
from datetime import date
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...auth import get_current_user, require_roles
from ...database import get_db
from ...models.conversation import Conversation, Message, MessageSender
from ...models.department import Department
from ...models.survey import Survey, SurveyResponse
from ...models.ticket import Ticket, TicketStatus
from ...models.user import User, UserRole, UserStatus
from ...models.leave_request import LeaveRequest, LeaveStatus as LeaveRowStatus
from ...models.hr_notification import HrNotification
from ...models.risk_snapshot import RiskSnapshot
from ...core.time import utcnow_naive

router = APIRouter(prefix="/portal", tags=["portal"])


def _dept_labels(db: Session) -> dict[str, str]:
    return {str(r.id): r.name for r in db.query(Department).all()}


def _leave_balance_for_user(db: Session, user_id) -> tuple[int, int, int]:
    """(annual_allowance, used_days_this_calendar_year, remaining)."""
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


class MeProfileResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    employee_id: Optional[str] = None
    designation: Optional[str] = None
    department: str
    manager_name: Optional[str] = None
    joined_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MeSummaryResponse(BaseModel):
    open_tickets: int
    total_tickets: int
    active_surveys: int
    surveys_answered: int
    last_chat_at: Optional[str] = None
    annual_leave_days: int = 25
    used_leave_days_ytd: int = 0
    leave_balance_remaining: int = 25


class ChatPreviewItem(BaseModel):
    id: str
    title: str
    preview: str
    when: str


class TimelineItem(BaseModel):
    date: str
    text: str
    tone: str


class TeamMemberItem(BaseModel):
    id: str
    name: str
    email: str
    initials: str
    role: str
    department: str
    sentiment: str
    risk_score: int = 0
    leave_balance: int
    open_tickets: int = 0
    needs_attention: bool = False


class ManagerSummaryItem(BaseModel):
    team_size: int
    at_risk_members: int
    watch_members: int
    pending_leave_requests: int
    open_team_tickets: int


class ActivityItem(BaseModel):
    text: str
    time: str
    tag: str
    tag_cls: str = "bg-secondary text-foreground"


class HrNotificationItem(BaseModel):
    id: str
    title: str
    body: str
    notification_type: str
    severity: str
    is_read: bool
    created_at: str


@router.get("/me/profile", response_model=MeProfileResponse)
def get_me_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dept = _dept_labels(db)
    dname = dept.get(str(current_user.department_id), "General") if current_user.department_id else "General"
    mgr = None
    if current_user.manager_id:
        m = db.query(User).filter(User.id == current_user.manager_id).first()
        if m:
            mgr = m.name
    return MeProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        employee_id=current_user.employee_id,
        designation=current_user.designation,
        department=dname,
        manager_name=mgr,
        joined_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


@router.get("/me/summary", response_model=MeSummaryResponse)
def get_me_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    open_n = (
        db.query(func.count(Ticket.id))
        .filter(
            Ticket.user_id == current_user.id,
            Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]),
        )
        .scalar()
        or 0
    )
    total_n = db.query(func.count(Ticket.id)).filter(Ticket.user_id == current_user.id).scalar() or 0

    active_surveys = db.query(func.count(Survey.id)).filter(Survey.is_active == True).scalar() or 0
    answered = (
        db.query(func.count(SurveyResponse.id))
        .filter(SurveyResponse.user_id == current_user.id)
        .scalar()
        or 0
    )

    last_msg = (
        db.query(func.max(Message.created_at))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == current_user.id)
        .scalar()
    )

    annual, used, remaining = _leave_balance_for_user(db, current_user.id)

    return MeSummaryResponse(
        open_tickets=int(open_n),
        total_tickets=int(total_n),
        active_surveys=int(active_surveys),
        surveys_answered=int(answered),
        last_chat_at=last_msg.isoformat() if last_msg else None,
        annual_leave_days=annual,
        used_leave_days_ytd=used,
        leave_balance_remaining=remaining,
    )


def _human_when(dt: Any) -> str:
    if not dt:
        return ""
    now = utcnow_naive()
    delta = now - dt
    secs = int(delta.total_seconds())
    if secs < 120:
        return "Just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    if delta.days == 1:
        return "1d ago"
    return f"{delta.days}d ago"


@router.get("/me/chats", response_model=List[ChatPreviewItem])
def list_my_recent_chats(
    limit: int = 8,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    limit = max(1, min(limit, 30))
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.started_at.desc())
        .limit(limit)
        .all()
    )
    out: List[ChatPreviewItem] = []
    for c in convs:
        last_user_msg = (
            db.query(Message)
            .filter(Message.conversation_id == c.id, Message.sender == MessageSender.user)
            .order_by(Message.created_at.desc())
            .first()
        )
        last_any = (
            db.query(Message)
            .filter(Message.conversation_id == c.id)
            .order_by(Message.created_at.desc())
            .first()
        )
        preview_src = last_user_msg or last_any
        preview = (preview_src.message_text[:120] + "…") if preview_src and len(preview_src.message_text) > 120 else (preview_src.message_text if preview_src else "")
        title = c.last_intent or c.active_flow or "Conversation"
        when = _human_when(last_any.created_at if last_any else c.started_at)
        out.append(ChatPreviewItem(id=str(c.id), title=str(title), preview=preview or "No messages yet", when=when))
    return out


@router.get("/me/timeline", response_model=List[TimelineItem])
def list_my_timeline(
    limit: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    limit = max(1, min(limit, 40))
    items: List[TimelineItem] = []

    tickets = (
        db.query(Ticket)
        .filter(Ticket.user_id == current_user.id)
        .order_by(Ticket.created_at.desc())
        .limit(8)
        .all()
    )
    for t in tickets:
        items.append(
            TimelineItem(
                date=t.created_at.date().isoformat() if t.created_at else "",
                text=f"Ticket: {(t.query or '')[:80]}",
                tone="neutral",
            )
        )

    responses = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.user_id == current_user.id)
        .order_by(SurveyResponse.created_at.desc())
        .limit(5)
        .all()
    )
    for r in responses:
        surv = db.query(Survey).filter(Survey.id == r.survey_id).first()
        title = surv.title if surv else "Survey"
        items.append(
            TimelineItem(
                date=r.created_at.date().isoformat() if r.created_at else "",
                text=f"Completed survey: {title}",
                tone="positive",
            )
        )

    for lv in (
        db.query(LeaveRequest)
        .filter(LeaveRequest.user_id == current_user.id)
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


@router.get("/manager/team", response_model=List[TeamMemberItem])
def list_my_direct_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dept = _dept_labels(db)
    reports = (
        db.query(User)
        .filter(User.manager_id == current_user.id, User.status == UserStatus.active)
        .order_by(User.name)
        .all()
    )
    latest_snapshots = (
        db.query(RiskSnapshot)
        .order_by(RiskSnapshot.user_id.asc(), RiskSnapshot.created_at.desc())
        .all()
    )
    snapshot_by_user: dict[str, RiskSnapshot] = {}
    for row in latest_snapshots:
        key = str(row.user_id)
        if key in snapshot_by_user:
            continue
        snapshot_by_user[key] = row

    out: List[TeamMemberItem] = []
    for u in reports:
        dname = dept.get(str(u.department_id), "General") if u.department_id else "General"
        initials = "".join(p[0] for p in (u.name or "NA").split()[:2]).upper()[:2] or "NA"
        _, _, remaining = _leave_balance_for_user(db, u.id)
        snapshot = snapshot_by_user.get(str(u.id))
        mood_score = float(snapshot.mood_score) if snapshot and snapshot.mood_score is not None else 60.0
        attrition_risk = float(snapshot.attrition_risk) if snapshot and snapshot.attrition_risk is not None else 0.0
        if mood_score >= 75:
            sentiment = "positive"
        elif mood_score >= 55:
            sentiment = "neutral"
        elif mood_score >= 35:
            sentiment = "watch"
        else:
            sentiment = "at_risk"
        open_tickets = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.user_id == u.id,
                Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]),
            )
            .scalar()
            or 0
        )
        risk_score = int(max(0, min(100, round(attrition_risk * 100))))
        out.append(
            TeamMemberItem(
                id=str(u.id),
                name=u.name,
                email=u.email or "",
                initials=initials,
                role=u.designation or "Employee",
                department=dname,
                sentiment=sentiment,
                risk_score=risk_score,
                leave_balance=int(remaining),
                open_tickets=int(open_tickets),
                needs_attention=(sentiment in {"watch", "at_risk"}) or open_tickets >= 2,
            )
        )
    return out


@router.get("/manager/summary", response_model=ManagerSummaryItem)
def get_manager_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report_ids = [
        row[0]
        for row in db.query(User.id)
        .filter(User.manager_id == current_user.id, User.status == UserStatus.active)
        .all()
    ]
    if not report_ids:
        return ManagerSummaryItem(
            team_size=0,
            at_risk_members=0,
            watch_members=0,
            pending_leave_requests=0,
            open_team_tickets=0,
        )

    latest_snapshots = (
        db.query(RiskSnapshot)
        .filter(RiskSnapshot.user_id.in_(report_ids))
        .order_by(RiskSnapshot.user_id.asc(), RiskSnapshot.created_at.desc())
        .all()
    )
    snapshot_by_user: dict[str, RiskSnapshot] = {}
    for row in latest_snapshots:
        key = str(row.user_id)
        if key in snapshot_by_user:
            continue
        snapshot_by_user[key] = row

    at_risk = 0
    watch = 0
    for uid in report_ids:
        snapshot = snapshot_by_user.get(str(uid))
        mood_score = float(snapshot.mood_score) if snapshot and snapshot.mood_score is not None else 60.0
        if mood_score < 35:
            at_risk += 1
        elif mood_score < 55:
            watch += 1

    pending_leave = (
        db.query(func.count(LeaveRequest.id))
        .filter(LeaveRequest.user_id.in_(report_ids), LeaveRequest.status == LeaveRowStatus.pending)
        .scalar()
        or 0
    )
    open_team_tickets = (
        db.query(func.count(Ticket.id))
        .filter(
            Ticket.user_id.in_(report_ids),
            Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]),
        )
        .scalar()
        or 0
    )
    return ManagerSummaryItem(
        team_size=len(report_ids),
        at_risk_members=int(at_risk),
        watch_members=int(watch),
        pending_leave_requests=int(pending_leave),
        open_team_tickets=int(open_team_tickets),
    )


@router.get("/hr/recent-activity", response_model=List[ActivityItem])
def hr_recent_activity(
    limit: int = 12,
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    limit = max(1, min(limit, 30))
    activity: List[ActivityItem] = []

    notifications = db.query(HrNotification).order_by(HrNotification.created_at.desc()).limit(limit).all()
    for n in notifications:
        when = _human_when(n.created_at)
        tag = (n.notification_type or "ticket_update").replace("_", " ")
        severity = (n.severity or "info").lower()
        tag_cls = (
            "bg-danger-soft text-danger"
            if severity in {"high", "critical"}
            else "bg-warning-soft text-warning"
            if severity in {"medium", "warning"}
            else "bg-secondary text-foreground"
        )
        activity.append(
            ActivityItem(
                text=f"{n.title}: {(n.body or '')[:70]}",
                time=when,
                tag=tag,
                tag_cls=tag_cls,
            )
        )

    if len(activity) >= limit:
        return activity[:limit]

    rows = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(limit).all()
    for t in rows:
        u = db.query(User).filter(User.id == t.user_id).first()
        who = u.name if u else "Someone"
        q = (t.query or "")[:70]
        when = _human_when(t.created_at)
        tag = str(t.status.value) if hasattr(t.status, "value") else str(t.status)
        tag_cls = (
            "bg-danger-soft text-danger"
            if t.status == TicketStatus.escalated
            else "bg-warning-soft text-warning"
            if t.status in (TicketStatus.open, TicketStatus.in_progress)
            else "bg-secondary text-foreground"
        )
        activity.append(
            ActivityItem(
                text=f"{who}: {q}",
                time=when,
                tag=tag.replace("_", " "),
                tag_cls=tag_cls,
            )
        )
    return activity[:limit]


@router.get("/hr/notifications", response_model=List[HrNotificationItem])
def hr_notifications(
    limit: int = 20,
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    limit = max(1, min(limit, 50))
    rows = db.query(HrNotification).order_by(HrNotification.created_at.desc()).limit(limit).all()
    return [
        HrNotificationItem(
            id=str(row.id),
            title=row.title or "Notification",
            body=row.body or "",
            notification_type=row.notification_type or "ticket_update",
            severity=row.severity or "info",
            is_read=bool(row.is_read),
            created_at=row.created_at.isoformat() if row.created_at else "",
        )
        for row in rows
    ]


@router.post("/hr/notifications/{notification_id}/read")
def mark_hr_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    row = db.query(HrNotification).filter(HrNotification.id == notification_id).first()
    if not row:
        return {"ok": False, "error": "Notification not found"}
    row.is_read = True
    row.read_at = utcnow_naive()
    db.commit()
    return {"ok": True}
