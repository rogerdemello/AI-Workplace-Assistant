from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...auth import get_current_user, require_roles
from ...database import get_db
from ...models.user import User
from ...services.automation_rules import AutomationRulesService
from ...services.mark_proactive import get_mark_proactive_service

router = APIRouter(prefix="/wellbeing", tags=["wellbeing"])


class ActivityEventCreate(BaseModel):
    event_type: str = Field(min_length=2, max_length=80)
    event_source: str = Field(default="web", max_length=40)
    activity_state: Optional[str] = Field(default=None, max_length=24)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActivityEventResponse(BaseModel):
    event_id: str
    event_type: str
    event_at: str
    nudge: Optional[str] = None


class ReminderCreate(BaseModel):
    reminder_type: str = Field(default="custom", min_length=2, max_length=32)
    title: str = Field(min_length=2, max_length=150)
    message: str = Field(min_length=2, max_length=1200)
    schedule_kind: str = Field(default="one_time")
    run_at: Optional[datetime] = None
    cron_expr: Optional[str] = Field(default=None, max_length=120)
    timezone: str = Field(default="UTC", max_length=64)
    payload: Dict[str, Any] = Field(default_factory=dict)


class ReminderUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=150)
    message: Optional[str] = Field(default=None, min_length=2, max_length=1200)
    status: Optional[str] = Field(default=None)
    schedule_kind: Optional[str] = Field(default=None)
    run_at: Optional[datetime] = None
    cron_expr: Optional[str] = Field(default=None, max_length=120)
    timezone: Optional[str] = Field(default=None, max_length=64)
    next_trigger_at: Optional[datetime] = None
    payload: Optional[Dict[str, Any]] = None


class ReminderResponse(BaseModel):
    id: str
    reminder_type: str
    title: str
    message: str
    schedule_kind: str
    run_at: Optional[datetime] = None
    cron_expr: Optional[str] = None
    timezone: str
    status: str
    next_trigger_at: Optional[datetime] = None
    last_triggered_at: Optional[datetime] = None
    created_at: datetime


class DailyCheckinRequest(BaseModel):
    mood: str = Field(default="okay")
    message: str = Field(default="")
    wants_followup: bool = False


class DailyCheckinResponse(BaseModel):
    mood: str
    signal: Dict[str, Any]
    suggested_next_step: str


class HighRiskEmployeeResponse(BaseModel):
    user_id: str
    name: str
    mood_score: float
    risk_score: float
    risk_level: str
    open_tickets: int
    last_active: str
    reasons: List[str]


class WeeklySummaryResponse(BaseModel):
    window_days: int
    high_risk_employees: int
    followup_signals: int
    open_tickets: int
    avg_engagement_score: float
    top_issues: List[Dict[str, Any]]

class ProactiveSuppressionPolicyResponse(BaseModel):
    enabled: bool
    global_daily_max: int
    break_nudge_cooldown_minutes: int
    break_nudge_daily_max: int
    scheduled_reminder_cooldown_minutes: int
    scheduled_reminder_daily_max: int
    daily_checkin_followup_cooldown_minutes: int
    daily_checkin_followup_daily_max: int


class ProactiveSuppressionPolicyUpdate(BaseModel):
    enabled: Optional[bool] = None
    global_daily_max: Optional[int] = Field(default=None, ge=1, le=50)
    break_nudge_cooldown_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    break_nudge_daily_max: Optional[int] = Field(default=None, ge=0, le=20)
    scheduled_reminder_cooldown_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    scheduled_reminder_daily_max: Optional[int] = Field(default=None, ge=0, le=50)
    daily_checkin_followup_cooldown_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    daily_checkin_followup_daily_max: Optional[int] = Field(default=None, ge=0, le=20)


def _to_reminder_response(row) -> ReminderResponse:
    return ReminderResponse(
        id=str(row.id),
        reminder_type=row.reminder_type,
        title=row.title,
        message=row.message,
        schedule_kind=row.schedule_kind,
        run_at=row.run_at,
        cron_expr=row.cron_expr,
        timezone=row.timezone,
        status=row.status,
        next_trigger_at=row.next_trigger_at,
        last_triggered_at=row.last_triggered_at,
        created_at=row.created_at,
    )


@router.post("/activity", response_model=ActivityEventResponse)
def track_activity(
    payload: ActivityEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = get_mark_proactive_service(db)
    result = service.track_activity_event(
        user_id=current_user.id,
        event_type=payload.event_type,
        event_source=payload.event_source,
        activity_state=payload.activity_state,
        metadata=payload.metadata,
    )
    try:
        AutomationRulesService(db).apply_event_rules(
            event_type="activity_event_tracked",
            context={
                "actor_id": current_user.id,
                "user_id": current_user.id,
                "event_type": payload.event_type,
                "activity_state": payload.activity_state,
                "nudge": result.get("nudge"),
            },
        )
        db.commit()
    except Exception:
        db.rollback()
    return ActivityEventResponse(**result)


@router.post("/check-ins/daily", response_model=DailyCheckinResponse, status_code=status.HTTP_201_CREATED)
def create_daily_checkin(
    payload: DailyCheckinRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = get_mark_proactive_service(db)
    result = service.record_daily_checkin(
        user_id=current_user.id,
        mood=payload.mood,
        message=payload.message,
        wants_followup=payload.wants_followup,
    )
    try:
        AutomationRulesService(db).apply_event_rules(
            event_type="daily_checkin_recorded",
            context={
                "actor_id": current_user.id,
                "user_id": current_user.id,
                "mood": payload.mood,
                "signal": result.get("signal") or {},
            },
        )
        db.commit()
    except Exception:
        db.rollback()
    return DailyCheckinResponse(**result)


@router.get("/reminders", response_model=List[ReminderResponse])
def list_reminders(
    include_cancelled: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = get_mark_proactive_service(db)
    rows = service.list_reminders(user_id=current_user.id, include_cancelled=include_cancelled)
    return [_to_reminder_response(r) for r in rows]


@router.post("/reminders", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = get_mark_proactive_service(db)
    try:
        row = service.create_reminder(
            user_id=current_user.id,
            reminder_type=payload.reminder_type,
            title=payload.title,
            message=payload.message,
            schedule_kind=payload.schedule_kind,
            run_at=payload.run_at,
            cron_expr=payload.cron_expr,
            timezone=payload.timezone,
            payload=payload.payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        AutomationRulesService(db).apply_event_rules(
            event_type="reminder_created",
            context={
                "actor_id": current_user.id,
                "user_id": current_user.id,
                "reminder": row,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
    return _to_reminder_response(row)


@router.patch("/reminders/{reminder_id}", response_model=ReminderResponse)
def update_reminder(
    reminder_id: UUID,
    payload: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = get_mark_proactive_service(db)
    updates = payload.model_dump(exclude_unset=True)
    row = service.update_reminder(user_id=current_user.id, reminder_id=reminder_id, updates=updates)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    try:
        AutomationRulesService(db).apply_event_rules(
            event_type="reminder_updated",
            context={
                "actor_id": current_user.id,
                "user_id": current_user.id,
                "reminder": row,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
    return _to_reminder_response(row)


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_reminder(
    reminder_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = get_mark_proactive_service(db)
    ok = service.cancel_reminder(user_id=current_user.id, reminder_id=reminder_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    try:
        AutomationRulesService(db).apply_event_rules(
            event_type="reminder_cancelled",
            context={
                "actor_id": current_user.id,
                "user_id": current_user.id,
                "reminder_id": str(reminder_id),
            },
        )
        db.commit()
    except Exception:
        db.rollback()
    return None


@router.get("/high-risk", response_model=List[HighRiskEmployeeResponse])
def list_high_risk_employees(
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    service = get_mark_proactive_service(db)
    rows = service.list_high_risk_users(limit=limit)
    return [HighRiskEmployeeResponse(**r) for r in rows]


@router.get("/weekly-summary", response_model=WeeklySummaryResponse)
def get_weekly_summary(
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    service = get_mark_proactive_service(db)
    return WeeklySummaryResponse(**service.build_weekly_hr_summary())


@router.get("/policy-suppression", response_model=ProactiveSuppressionPolicyResponse)
def get_proactive_suppression_policy(
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    service = get_mark_proactive_service(db)
    return ProactiveSuppressionPolicyResponse(**service.get_suppression_policy())


@router.patch("/policy-suppression", response_model=ProactiveSuppressionPolicyResponse)
def update_proactive_suppression_policy(
    payload: ProactiveSuppressionPolicyUpdate,
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    service = get_mark_proactive_service(db)
    updates = payload.model_dump(exclude_unset=True)
    return ProactiveSuppressionPolicyResponse(**service.update_suppression_policy(updates))
