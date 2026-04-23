"""HR Dashboard routes — powered by Postgres (SQLAlchemy), not raw Supabase."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import logging

from ..core.auth import get_hr_context
from ..database import get_db
from ..models.conversation import Conversation, Message, MessageSender, SentimentLabel
from ..core.time import utcnow_naive
from ..models.user import User, UserRole, UserStatus
from ..services.dashboard_analytics import (
    build_ai_summary,
    compute_kpi_overview,
    compute_weekly_quality,
    employee_insights_for_hr,
    sentiment_trend_days,
)
from ..models.hr_alert import HrAlert
from ..api.v1.hr_alerts import _store_from_wellbeing

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hr-dashboard"])


# ─────────────────────────────────────────────────────────────────────────────
# eNPS helper  (derived from sentiment distribution in messages)
# ─────────────────────────────────────────────────────────────────────────────
def _compute_enps(db: Session, window_days: int = 30) -> float:
    """
    Proxy eNPS from message sentiment.
    Promoters:  positive sentiment
    Detractors: negative sentiment
    Passives:   neutral sentiment
    eNPS = (promoters% - detractors%)  → range -100 to 100
    """
    since = utcnow_naive() - timedelta(days=window_days)
    rows = (
        db.query(Message.sentiment)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Message.sender == MessageSender.user,
            Message.sentiment.isnot(None),
            Message.created_at >= since,
        )
        .all()
    )
    if not rows:
        return 0.0

    total = len(rows)
    promoters = sum(1 for r in rows if r[0] == SentimentLabel.positive)
    detractors = sum(1 for r in rows if r[0] == SentimentLabel.negative)
    enps = ((promoters - detractors) / total) * 100.0
    return round(enps, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Department sentiment breakdown helper
# ─────────────────────────────────────────────────────────────────────────────
def _department_breakdown(db: Session, window_days: int = 30) -> List[Dict[str, Any]]:
    """Return avg sentiment score per department."""
    since = utcnow_naive() - timedelta(days=window_days)
    rows = (
        db.query(User.department_id, Message.sentiment)
        .join(Conversation, Conversation.user_id == User.id)
        .join(Message, Message.conversation_id == Conversation.id)
        .filter(
            Message.sender == MessageSender.user,
            Message.sentiment.isnot(None),
            Message.created_at >= since,
        )
        .all()
    )

    dept_buckets: Dict[str, Dict[str, int]] = defaultdict(lambda: {"positive": 0, "neutral": 0, "negative": 0})
    for dept_id, sentiment in rows:
        key = str(dept_id) if dept_id else "General"
        if sentiment == SentimentLabel.positive:
            dept_buckets[key]["positive"] += 1
        elif sentiment == SentimentLabel.negative:
            dept_buckets[key]["negative"] += 1
        else:
            dept_buckets[key]["neutral"] += 1

    # Try to map department IDs to names
    from ..models.department import Department  # lazy import
    dept_names: Dict[str, str] = {}
    try:
        for d in db.query(Department).all():
            dept_names[str(d.id)] = d.name
    except Exception:
        pass

    result = []
    for dept_key, counts in dept_buckets.items():
        total = counts["positive"] + counts["neutral"] + counts["negative"]
        if total == 0:
            continue
        score = round(((counts["positive"] - counts["negative"]) / total) * 100, 1)
        result.append(
            {
                "department": dept_names.get(dept_key, dept_key),
                "positive": round(counts["positive"] / total * 100, 1),
                "neutral": round(counts["neutral"] / total * 100, 1),
                "negative": round(counts["negative"] / total * 100, 1),
                "score": score,
                "total_messages": total,
            }
        )

    result.sort(key=lambda x: x["score"])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(
    user: dict = Depends(get_hr_context),
    db: Session = Depends(get_db),
):
    """
    Full HR dashboard payload.
    Returns: engagement_score, enps, risk_level, open_tickets,
             sentiment_trend (14 days), department_breakdown,
             employee_insights, ai_summary, weekly_quality.
    """
    kpi = compute_kpi_overview(db)
    enps = _compute_enps(db, window_days=30)
    trend = sentiment_trend_days(db, days=14)
    dept_breakdown = _department_breakdown(db, window_days=30)
    employees = employee_insights_for_hr(db, limit=50)
    high_risk_now = [e for e in employees if e.get("risk_score", 0) >= 70]
    if high_risk_now:
        try:
            recent_cutoff = utcnow_naive() - timedelta(minutes=30)
            recent_auto = (
                db.query(HrAlert.id)
                .filter(
                    HrAlert.source == "proactive_wellbeing",
                    HrAlert.created_at >= recent_cutoff,
                )
                .first()
            )
            if not recent_auto:
                _store_from_wellbeing(db)
        except Exception:
            logger.warning("Auto wellbeing alert generation skipped", exc_info=True)

    ai_summary = build_ai_summary(db, open_tickets=kpi["open_tickets"])
    weekly_quality = compute_weekly_quality(db, window_days=7)

    # Derive attrition_risk from engagement and high-risk employee count
    high_risk_count = sum(1 for e in employees if e.get("risk_score", 0) >= 70)
    total = len(employees)
    attrition_risk_pct = round((high_risk_count / total) * 100, 1) if total > 0 else 0.0

    return {
        "engagement_score": kpi["engagement_score"],
        "enps": enps,
        "risk_level": (
            "Low" if len(employees) == 0
            else "High" if kpi["engagement_score"] < 50
            else "Medium" if kpi["engagement_score"] < 70
            else "Low"
        ),
        "attrition_risk_pct": attrition_risk_pct,
        "open_tickets": kpi["open_tickets"],
        "total_tickets": kpi["total_tickets"],
        "active_users": kpi["active_users"],
        "resolution_rate": kpi["resolution_rate"],
        "avg_response_time": kpi["avg_response_time"],
        "sentiment_trend": trend,
        "department_breakdown": dept_breakdown,
        "employees": employees,
        "ai_summary": ai_summary,
        "weekly_quality": weekly_quality,
    }


@router.get("/sentiment-trend")
def sentiment_trend(
    days: int = 14,
    user: dict = Depends(get_hr_context),
    db: Session = Depends(get_db),
):
    return sentiment_trend_days(db, days=max(1, min(days, 90)))


@router.get("/department-breakdown")
def department_breakdown(
    days: int = 30,
    user: dict = Depends(get_hr_context),
    db: Session = Depends(get_db),
):
    return _department_breakdown(db, window_days=max(1, min(days, 90)))


@router.get("/enps")
def get_enps(
    days: int = 30,
    user: dict = Depends(get_hr_context),
    db: Session = Depends(get_db),
):
    return {"enps": _compute_enps(db, window_days=max(1, min(days, 90)))}
