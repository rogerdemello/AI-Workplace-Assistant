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
from ...models.sentiment_log import SentimentLog
from ...models.mood_entry import MoodEntry
from ...models.conversation import Message, MessageSender, Conversation
from datetime import datetime as _dt, timedelta as _td
import logging

logger = logging.getLogger(__name__)

# Single-word acks / fillers carry sentiment but no signal — keep them off
# the HR timeline so it reads as meaningful events, not noise.
_TRIVIAL_REPLIES = {
    "yeah", "yes", "yep", "y", "no", "nope", "n", "ok", "okay", "k",
    "sure", "thx", "thanks", "ty", "cool", "nice", "lol", "haha", "hmm",
}

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


class UserSelfUpdate(BaseModel):
    name: Optional[str] = None
    designation: Optional[str] = None


class UserAdminUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    designation: Optional[str] = None
    department_id: Optional[str] = None
    manager_id: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


@router.patch("/me", response_model=UserListItem)
def update_my_profile(
    payload: UserSelfUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Self-service profile edit (name, designation only)."""
    changed = False
    if payload.name is not None and payload.name.strip():
        current_user.name = payload.name.strip()
        changed = True
    if payload.designation is not None:
        current_user.designation = payload.designation.strip() or None
        changed = True

    if changed:
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

    dept = _dept_map(db)
    dname = dept.get(str(current_user.department_id), "General") if current_user.department_id else "General"
    return UserListItem(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        employee_id=current_user.employee_id,
        designation=current_user.designation,
        department=dname,
        status=current_user.status.value if hasattr(current_user.status, "value") else str(current_user.status),
    )


@router.patch("/{user_id}", response_model=UserListItem)
def admin_update_user(
    user_id: UUID,
    payload: UserAdminUpdate,
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    """Admin/HR: update any user. Role/status/department changes go through here."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Capture pre-update values so we can fire lifecycle check-ins on real
    # changes — manager re-assignment / role move are exactly the moments
    # Infeedo-style listening cares about.
    old_manager_id = u.manager_id
    old_designation = u.designation

    if payload.name is not None and payload.name.strip():
        u.name = payload.name.strip()
    if payload.email is not None and payload.email.strip():
        u.email = payload.email.strip().lower()
    if payload.designation is not None:
        u.designation = payload.designation.strip() or None
    if payload.department_id is not None:
        u.department_id = payload.department_id or None
    if payload.manager_id is not None:
        u.manager_id = payload.manager_id or None
    if payload.role is not None:
        try:
            u.role = UserRole(payload.role)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {payload.role}")
    if payload.status is not None:
        try:
            u.status = UserStatus(payload.status)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status: {payload.status}")

    db.add(u)
    db.commit()
    db.refresh(u)

    # Best-effort lifecycle check-ins — failures must not break the PATCH.
    try:
        from ...services.lifecycle_surveys import enqueue_lifecycle_check_in
        if u.manager_id != old_manager_id and u.manager_id is not None:
            enqueue_lifecycle_check_in(
                db,
                user_id=u.id,
                kind="manager_change",
                message_text="Heads up — your reporting line just changed. How's it been working with your new manager so far?",
            )
        if (u.designation or "") != (old_designation or "") and u.designation:
            enqueue_lifecycle_check_in(
                db,
                user_id=u.id,
                kind="role_change",
                message_text=f"You've moved into '{u.designation}'. How's the new role feeling so far?",
            )
    except Exception:
        logger.warning("Lifecycle check-in enqueue failed", exc_info=True)

    dept = _dept_map(db)
    dname = dept.get(str(u.department_id), "General") if u.department_id else "General"
    return UserListItem(
        id=str(u.id),
        email=u.email,
        name=u.name,
        role=u.role.value if hasattr(u.role, "value") else str(u.role),
        employee_id=u.employee_id,
        designation=u.designation,
        department=dname,
        status=u.status.value if hasattr(u.status, "value") else str(u.status),
    )


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
    # (timestamp, TimelineItem) so same-day events sort correctly by time, not
    # by insertion order or stringly-typed date.
    sortable: List[tuple[_dt, TimelineItem]] = []

    def _iso(d: _dt | None) -> str:
        return d.date().isoformat() if d else ""

    # Tickets — hide anonymous ones from the user's own timeline (the whole
    # point of an anonymous report is that it isn't attributable here).
    for t in (
        db.query(Ticket)
        .filter(Ticket.user_id == user_id, Ticket.is_anonymous.is_(False))
        .order_by(Ticket.created_at.desc())
        .limit(8)
        .all()
    ):
        sortable.append((
            t.created_at or _dt.min,
            TimelineItem(date=_iso(t.created_at), text=f"Ticket: {(t.query or '')[:80]}", tone="neutral"),
        ))

    for r in (
        db.query(SurveyResponse)
        .filter(SurveyResponse.user_id == user_id)
        .order_by(SurveyResponse.created_at.desc())
        .limit(5)
        .all()
    ):
        surv = db.query(Survey).filter(Survey.id == r.survey_id).first()
        title = surv.title if surv else "Survey"
        sortable.append((
            r.created_at or _dt.min,
            TimelineItem(date=_iso(r.created_at), text=f"Survey response: {title}", tone="positive"),
        ))

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
        sortable.append((
            lv.created_at or _dt.min,
            TimelineItem(
                date=_iso(lv.created_at),
                text=f"Leave ({st}): {lv.start_date} → {lv.end_date} ({lt_label})",
                tone=tone,
            ),
        ))

    # Chat-derived sentiment signals.
    # Pull more than 8 so we can drop dupes / "yeah" noise without coming up empty.
    sentiment_rows = (
        db.query(
            SentimentLog,
            Message.message_text,
            Message.conversation_id,
            Message.created_at.label("msg_at"),
        )
        .outerjoin(Message, Message.id == SentimentLog.message_id)
        .filter(SentimentLog.employee_id == user_id)
        .filter(SentimentLog.label.in_(("positive", "negative")))
        .order_by(SentimentLog.created_at.desc())
        .limit(24)
        .all()
    )

    # One query to find recent "Pulse check:" bot messages — used in Python to
    # tag sentiment items that follow a pulse question within ~60 minutes.
    pulse_cutoff = _dt.utcnow() - _td(days=30)
    pulse_by_conv: dict[str, List[_dt]] = {}
    for cid, cat in (
        db.query(Message.conversation_id, Message.created_at)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.user_id == user_id)
        .filter(Message.sender == MessageSender.bot)
        .filter(Message.message_text.contains("Pulse check:"))
        .filter(Message.created_at >= pulse_cutoff)
        .all()
    ):
        pulse_by_conv.setdefault(str(cid), []).append(cat)

    seen_msg_ids: set[str] = set()
    seen_norm_texts: set[str] = set()
    sentiment_added = 0
    for sl, msg_text, msg_conv_id, msg_at in sentiment_rows:
        if sentiment_added >= 8:
            break
        text_raw = (msg_text or "").strip()
        if not text_raw:
            continue
        norm = text_raw.lower().rstrip("!.?").strip()
        # Strip stray apostrophes/spaces so "what's a..." and "whats a..." collapse.
        norm_key = "".join(ch for ch in norm if ch.isalnum() or ch == " ").strip()
        norm_key = " ".join(norm_key.split())
        if norm in _TRIVIAL_REPLIES or len(norm) < 4:
            continue
        mkey = str(sl.message_id)
        if mkey in seen_msg_ids or norm_key in seen_norm_texts:
            continue
        seen_msg_ids.add(mkey)
        if norm_key:
            seen_norm_texts.add(norm_key)

        is_pulse_reply = False
        if msg_conv_id and msg_at:
            for pulse_at in pulse_by_conv.get(str(msg_conv_id), []):
                if pulse_at and pulse_at < msg_at and (msg_at - pulse_at).total_seconds() <= 3600:
                    is_pulse_reply = True
                    break

        emotion_raw = (sl.emotion or "").strip()
        if emotion_raw and emotion_raw != "neutral":
            descriptor = emotion_raw
        else:
            descriptor = "upbeat" if sl.label == "positive" else "down"

        snippet = text_raw.replace("\n", " ")
        if len(snippet) > 60:
            snippet = snippet[:60].rstrip() + "…"

        prefix = "Pulse reply" if is_pulse_reply else "Chat"
        sortable.append((
            sl.created_at or _dt.min,
            TimelineItem(
                date=_iso(sl.created_at),
                text=f"{prefix}: {descriptor} — “{snippet}”",
                tone="positive" if sl.label == "positive" else "danger",
            ),
        ))
        sentiment_added += 1

    # Mood check-ins (employee's own daily self-report). Skip bogus scores so
    # stale demo rows like "🙂 (4/100)" don't surface as danger.
    for me in (
        db.query(MoodEntry)
        .filter(MoodEntry.user_id == user_id)
        .order_by(MoodEntry.created_at.desc())
        .limit(5)
        .all()
    ):
        score = int(me.mood_score or 0)
        # Drop obviously-malformed scores (0, negative, >100, or on a 1–5 scale
        # rather than 0–100 — frontend mood chips use 80/55/35/15).
        if score < 10 or score > 100:
            continue
        emoji = me.mood_emoji.value if hasattr(me.mood_emoji, "value") else str(me.mood_emoji)
        if score >= 70:
            mtone = "positive"
        elif score <= 35:
            mtone = "danger"
        else:
            mtone = "neutral"
        sortable.append((
            me.created_at or _dt.min,
            TimelineItem(date=_iso(me.created_at), text=f"Mood check-in: {emoji} ({score}/100)", tone=mtone),
        ))

    sortable.sort(key=lambda kv: kv[0], reverse=True)
    return [item for _ts, item in sortable[:limit]]


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
