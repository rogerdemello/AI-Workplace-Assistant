"""
HR dashboard metrics from Postgres (tickets, messages, users).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID
import re

from sqlalchemy import case, cast, func, or_
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session
from sqlalchemy.types import Date

from ..models.conversation import Conversation, Message, MessageSender, SentimentLabel
from ..core.time import utcnow_naive

#: Human labels for the stored risk components, in the order HR reads them.
_RISK_FACTOR_LABELS = {
    "negativity": "Negative sentiment",
    "inactivity": "Inactivity",
    "complaints": "Complaint signals",
    "trend_drop": "Falling trend",
    "sustained_negative_bump": "Sustained negative pattern",
}

#: Below this many messages in 30 days, a score is a guess dressed as a number.
_LOW_CONFIDENCE_MESSAGES = 5
_HIGH_CONFIDENCE_MESSAGES = 20


def _explain_risk(risk_factors: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Turn stored risk components into something HR can act on.

    Returns the top contributors in points, plus how much data the score rests
    on. A risk score of 46 built entirely from "hasn't messaged in two weeks"
    means something completely different from one built from repeated distress,
    and the number alone cannot tell them apart.
    """
    empty = {
        "top_factors": [],
        "confidence": 0.0,
        "band": "low_confidence",
        "factors": None,
    }
    if not isinstance(risk_factors, dict):
        return empty

    contributions = risk_factors.get("contributions")
    if not isinstance(contributions, dict):
        return empty

    ranked = sorted(
        ((k, float(v or 0)) for k, v in contributions.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )
    top = [
        f"{_RISK_FACTOR_LABELS.get(name, name)} ({value:.0f} pts)"
        for name, value in ranked
        if value > 0
    ][:3]

    messages_30d = 0
    confidence_block = risk_factors.get("confidence")
    if isinstance(confidence_block, dict):
        try:
            messages_30d = int(confidence_block.get("messages_30d") or 0)
        except (TypeError, ValueError):
            messages_30d = 0

    confidence = min(1.0, messages_30d / float(_HIGH_CONFIDENCE_MESSAGES))
    if messages_30d < _LOW_CONFIDENCE_MESSAGES:
        band = "low_confidence"
    elif messages_30d < _HIGH_CONFIDENCE_MESSAGES:
        band = "medium_confidence"
    else:
        band = "high_confidence"

    return {
        "top_factors": top,
        "confidence": round(confidence, 2),
        "band": band,
        "factors": risk_factors,
    }
from ..models.analytics import MentalHealthScore
from ..models.chat_feedback import ChatFeedback
from ..models.department import Department
from ..models.employee_score import EmployeeScore
from ..models.message_signal import MessageSignal
from ..models.sentiment_log import SentimentLog
from ..models.risk_snapshot import RiskSnapshot
from ..models.survey import SurveyResponse
from ..models.ticket import Ticket, TicketStatus
from ..models.user import User, UserRole, UserStatus
from ..config import settings
from .attrition import AttritionRiskService


def _resolved_filter():
    return or_(Ticket.status == TicketStatus.resolved, Ticket.status == TicketStatus.closed)


def compute_kpi_overview(db: Session) -> Dict[str, Any]:
    total_tickets = db.query(func.count(Ticket.id)).scalar() or 0
    resolved = db.query(func.count(Ticket.id)).filter(_resolved_filter()).scalar() or 0
    open_tickets = (
        db.query(func.count(Ticket.id))
        .filter(
            Ticket.status.in_(
                [TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]
            )
        )
        .scalar()
        or 0
    )

    resolution_rate = (resolved / total_tickets) if total_tickets else 0.0

    # Avg hours to resolve when resolved_at is set
    resolved_rows = (
        db.query(Ticket.created_at, Ticket.resolved_at)
        .filter(_resolved_filter(), Ticket.resolved_at.isnot(None))
        .all()
    )
    if resolved_rows:
        deltas = [
            (r.resolved_at - r.created_at).total_seconds() / 3600.0
            for r in resolved_rows
            if r.resolved_at and r.created_at
        ]
        avg_response_time = sum(deltas) / len(deltas) if deltas else 0.0
    else:
        avg_response_time = 0.0

    since = utcnow_naive() - timedelta(days=30)
    active_users = (
        db.query(func.count(func.distinct(Conversation.user_id)))
        .join(Message, Message.conversation_id == Conversation.id)
        .filter(Message.created_at >= since)
        .scalar()
        or 0
    )
    if active_users == 0:
        active_users = (
            db.query(func.count(func.distinct(Ticket.user_id))).filter(Ticket.created_at >= since).scalar()
            or 0
        )

    total_employees = (
        db.query(func.count(User.id)).filter(User.role == UserRole.employee, User.status == UserStatus.active).scalar()
        or 0
    )

    from .engagement_score import EngagementScore

    engagement_service = EngagementScore(db)
    users = (
        db.query(User)
        .filter(User.role == UserRole.employee, User.status == UserStatus.active)
        .all()
    )
    if users:
        scores = [
            engagement_service.calculate_user_engagement(u.id, days=30)["engagement_score"]
            for u in users
        ]
        engagement_score = round(sum(scores) / len(scores), 1)
    else:
        engagement_score = 0.0

    def _extract_nps_score(responses: dict) -> Optional[int]:
        if not responses:
            return None
        for key, val in responses.items():
            if isinstance(val, (int, float)) and 0 <= val <= 10:
                return int(val)
        return None

    enps_since = utcnow_naive() - timedelta(days=30)
    survey_responses = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.created_at >= enps_since)
        .all()
    )
    nps_scores = []
    for r in survey_responses:
        score = _extract_nps_score(r.responses or {})
        if score is not None:
            nps_scores.append(score)
    if nps_scores:
        promoters = sum(1 for s in nps_scores if s >= 9)
        detractors = sum(1 for s in nps_scores if s <= 6)
        enps = round(((promoters - detractors) / len(nps_scores)) * 100.0, 1)
    else:
        enps = 0.0

    return {
        "engagement_score": engagement_score,
        "resolution_rate": round(resolution_rate, 3),
        "avg_response_time": round(avg_response_time, 2),
        "active_users": int(active_users),
        "total_tickets": int(total_tickets),
        "open_tickets": int(open_tickets),
        "enps": enps,
    }


def compute_kpi_window(db: Session, since: datetime, until: datetime) -> Dict[str, Any]:
    """KPI counters scoped to a single time window.

    Returns flow metrics — new tickets, resolved tickets, active employees,
    avg sentiment — within ``[since, until)``. The current at-risk headcount
    is computed off the latest EmployeeScore rows and is not scoped to the
    window (snapshot, not flow).
    """
    new_tickets = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.created_at >= since, Ticket.created_at < until)
        .scalar()
        or 0
    )
    resolved_tickets = (
        db.query(func.count(Ticket.id))
        .filter(
            _resolved_filter(),
            Ticket.resolved_at.isnot(None),
            Ticket.resolved_at >= since,
            Ticket.resolved_at < until,
        )
        .scalar()
        or 0
    )
    active_employees = (
        db.query(func.count(func.distinct(Conversation.user_id)))
        .join(Message, Message.conversation_id == Conversation.id)
        .filter(Message.created_at >= since, Message.created_at < until)
        .scalar()
        or 0
    )

    avg_sentiment_raw = (
        db.query(func.avg(SentimentLog.score))
        .filter(SentimentLog.created_at >= since, SentimentLog.created_at < until)
        .scalar()
    )
    avg_sentiment = round(float(avg_sentiment_raw), 1) if avg_sentiment_raw is not None else None

    return {
        "new_tickets": int(new_tickets),
        "resolved_tickets": int(resolved_tickets),
        "active_employees": int(active_employees),
        "avg_sentiment": avg_sentiment,
    }


def compute_at_risk_count(db: Session, threshold: float = 70.0) -> int:
    """Number of employees with a current risk_score at or above ``threshold``."""
    return (
        db.query(func.count(EmployeeScore.employee_id))
        .filter(EmployeeScore.risk_score >= threshold)
        .scalar()
        or 0
    )


def compute_department_heatmap(db: Session) -> List[Dict[str, Any]]:
    """Group employees into sentiment buckets per department.

    Buckets are derived from EmployeeScore:
      * at_risk  — sentiment_score < 40 OR risk_score >= 70
      * watch    — 40 <= sentiment_score < 60 (and not at_risk)
      * positive — sentiment_score >= 60 (and not at_risk)

    Users with no EmployeeScore row are counted in ``unknown``. Users with no
    department are grouped under a synthetic "Unassigned" department.
    """
    bucket = case(
        (
            or_(EmployeeScore.sentiment_score < 40, EmployeeScore.risk_score >= 70),
            "at_risk",
        ),
        (EmployeeScore.sentiment_score < 60, "watch"),
        (EmployeeScore.sentiment_score.isnot(None), "positive"),
        else_="unknown",
    ).label("bucket")

    rows = (
        db.query(
            User.department_id.label("department_id"),
            bucket,
            func.count(User.id).label("count"),
            func.avg(EmployeeScore.sentiment_score).label("avg_sentiment"),
        )
        .outerjoin(EmployeeScore, EmployeeScore.employee_id == User.id)
        .filter(User.role == UserRole.employee, User.status == UserStatus.active)
        .group_by(User.department_id, "bucket")
        .all()
    )

    departments = {str(d.id): d.name for d in db.query(Department).all()}

    by_dept: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        dept_id = str(r.department_id) if r.department_id else "unassigned"
        dept_name = departments.get(dept_id, "Unassigned") if r.department_id else "Unassigned"
        entry = by_dept.setdefault(
            dept_id,
            {
                "department_id": dept_id if r.department_id else None,
                "department_name": dept_name,
                "positive": 0,
                "watch": 0,
                "at_risk": 0,
                "unknown": 0,
                "_sentiment_sum": 0.0,
                "_sentiment_n": 0,
            },
        )
        entry[str(r.bucket)] = int(r.count)
        if r.avg_sentiment is not None and r.bucket != "unknown":
            entry["_sentiment_sum"] += float(r.avg_sentiment) * int(r.count)
            entry["_sentiment_n"] += int(r.count)

    out: List[Dict[str, Any]] = []
    for entry in by_dept.values():
        total = entry["positive"] + entry["watch"] + entry["at_risk"] + entry["unknown"]
        avg = (
            round(entry["_sentiment_sum"] / entry["_sentiment_n"], 1)
            if entry["_sentiment_n"] > 0
            else None
        )
        out.append(
            {
                "department_id": entry["department_id"],
                "department_name": entry["department_name"],
                "total": total,
                "positive": entry["positive"],
                "watch": entry["watch"],
                "at_risk": entry["at_risk"],
                "unknown": entry["unknown"],
                "avg_sentiment": avg,
            }
        )
    out.sort(key=lambda d: (-d["at_risk"], -d["total"], d["department_name"] or ""))
    return out


def sentiment_trend_days(db: Session, days: int = 14) -> List[Dict[str, Any]]:
    days = max(1, min(days, 90))
    start = utcnow_naive() - timedelta(days=days - 1)
    # func.date() is the portable pattern used elsewhere in this module; the
    # earlier cast(..., Date) broke SQLite result processing (fromisoformat).
    day_key = func.date(Message.created_at)

    rows = (
        db.query(day_key, Message.sentiment, func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Message.created_at >= start, Message.sender == MessageSender.user)
        .group_by(day_key, Message.sentiment)
        .all()
    )

    by_date: Dict[str, Dict[str, int]] = defaultdict(lambda: {"positive": 0, "neutral": 0, "negative": 0})
    for d, sent, cnt in rows:
        if d is None:
            continue
        key = d.isoformat() if hasattr(d, "isoformat") else str(d)
        label = "neutral"
        if sent == SentimentLabel.positive:
            label = "positive"
        elif sent == SentimentLabel.negative:
            label = "negative"
        elif sent == SentimentLabel.neutral:
            label = "neutral"
        by_date[key][label] += int(cnt)

    out: List[Dict[str, Any]] = []
    for i in range(days):
        d = (utcnow_naive() - timedelta(days=days - 1 - i)).date()
        key = d.isoformat()
        bucket = by_date.get(key, {"positive": 0, "neutral": 0, "negative": 0})
        total = bucket["positive"] + bucket["neutral"] + bucket["negative"]
        if total == 0:
            out.append({"date": key, "positive": 0.0, "neutral": 0.0, "negative": 0.0})
        else:
            out.append(
                {
                    "date": key,
                    "positive": round(100.0 * bucket["positive"] / total, 1),
                    "neutral": round(100.0 * bucket["neutral"] / total, 1),
                    "negative": round(100.0 * bucket["negative"] / total, 1),
                }
            )
    return out


def emotion_trend_days(db: Session, days: int = 14) -> List[Dict[str, Any]]:
    """Daily distribution of logged emotions from sentiment_logs."""
    days = max(1, min(days, 90))
    start = utcnow_naive() - timedelta(days=days - 1)
    day_key = func.date(SentimentLog.created_at)
    rows = (
        db.query(day_key, SentimentLog.emotion, func.count(SentimentLog.id))
        .filter(SentimentLog.created_at >= start)
        .group_by(day_key, SentimentLog.emotion)
        .all()
    )

    by_date: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for d, emotion, cnt in rows:
        if d is None:
            continue
        key = str(d)
        label = str(emotion or "neutral")
        by_date[key][label] += int(cnt)

    out: List[Dict[str, Any]] = []
    for i in range(days):
        d = (utcnow_naive() - timedelta(days=days - 1 - i)).date()
        key = d.isoformat()
        bucket = dict(by_date.get(key, {}))
        total = sum(bucket.values())
        if total == 0:
            out.append({"date": key, "emotions": {}})
            continue
        percentages = {
            emotion: round((count / total) * 100.0, 1)
            for emotion, count in sorted(bucket.items(), key=lambda item: item[1], reverse=True)
        }
        out.append({"date": key, "emotions": percentages})
    return out


def emotion_trend_days_for_manager(db: Session, manager_id: UUID, days: int = 14) -> List[Dict[str, Any]]:
    """Daily emotion mix from sentiment_logs for direct reports only."""
    days = max(1, min(days, 90))
    start = utcnow_naive() - timedelta(days=days - 1)
    day_key = func.date(SentimentLog.created_at)
    rows = (
        db.query(day_key, SentimentLog.emotion, func.count(SentimentLog.id))
        .join(User, User.id == SentimentLog.employee_id)
        .filter(
            SentimentLog.created_at >= start,
            User.manager_id == manager_id,
            User.role == UserRole.employee,
            User.status == UserStatus.active,
        )
        .group_by(day_key, SentimentLog.emotion)
        .all()
    )

    by_date: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for d, emotion, cnt in rows:
        if d is None:
            continue
        key = str(d)
        label = str(emotion or "neutral")
        by_date[key][label] += int(cnt)

    out: List[Dict[str, Any]] = []
    for i in range(days):
        d = (utcnow_naive() - timedelta(days=days - 1 - i)).date()
        key = d.isoformat()
        bucket = dict(by_date.get(key, {}))
        total = sum(bucket.values())
        if total == 0:
            out.append({"date": key, "emotions": {}})
            continue
        percentages = {
            emotion: round((count / total) * 100.0, 1)
            for emotion, count in sorted(bucket.items(), key=lambda item: item[1], reverse=True)
        }
        out.append({"date": key, "emotions": percentages})
    return out


def _human_last_active(dt: Optional[datetime]) -> str:
    if not dt:
        return "Recently"
    delta = utcnow_naive() - dt
    if delta.total_seconds() < 120:
        return "Just now"
    if delta.total_seconds() < 3600:
        return f"{int(delta.total_seconds() // 60)} mins ago"
    if delta.total_seconds() < 86400:
        return f"{int(delta.total_seconds() // 3600)} hours ago"
    if delta.days == 1:
        return "1 day ago"
    return f"{delta.days} days ago"


def employee_insights_for_hr(db: Session, limit: int = 50) -> List[Dict[str, Any]]:
    """Employees + sentiment/risk derived from messages and tickets (batched for performance)."""
    limit = max(1, min(limit, 200))

    dept_name = {str(r.id): r.name for r in db.query(Department).all()}

    users = (
        db.query(User)
        .filter(User.role == UserRole.employee, User.status == UserStatus.active)
        .order_by(User.updated_at.desc())
        .limit(limit)
        .all()
    )
    if not users:
        user_ids = [row[0] for row in db.query(func.distinct(Ticket.user_id)).limit(limit).all()]
        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []

    if not users:
        return []

    user_ids = [u.id for u in users]
    now = utcnow_naive()
    sustained_wd = max(1, int(settings.SUSTAINED_NEGATIVE_WINDOW_DAYS))
    sustained_start = now - timedelta(days=sustained_wd)
    min_sustained = max(1, int(settings.SUSTAINED_NEGATIVE_MIN_MESSAGES))

    # Bulk fetch all related data
    scores = {s.employee_id: s for s in db.query(EmployeeScore).filter(EmployeeScore.employee_id.in_(user_ids)).all()}
    risk_snaps = {}
    for rs in db.query(RiskSnapshot).filter(RiskSnapshot.user_id.in_(user_ids)).order_by(RiskSnapshot.created_at.desc()).all():
        if rs.user_id not in risk_snaps:
            risk_snaps[rs.user_id] = rs
    mh_scores = {}
    for mh in db.query(MentalHealthScore).filter(MentalHealthScore.user_id.in_(user_ids)).order_by(MentalHealthScore.created_at.desc()).all():
        if mh.user_id not in mh_scores:
            mh_scores[mh.user_id] = mh

    # Bulk fetch latest message timestamps per user
    latest_msg_subq = (
        db.query(Conversation.user_id, func.max(Message.created_at).label("last_msg_at"))
        .join(Message, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id.in_(user_ids))
        .group_by(Conversation.user_id)
        .subquery()
    )
    latest_msg_map = {row.user_id: row.last_msg_at for row in db.query(latest_msg_subq).all()}

    # Bulk fetch open ticket counts per user
    open_ticket_counts = {}
    for row in (
        db.query(Ticket.user_id, func.count(Ticket.id).label("cnt"))
        .filter(
            Ticket.user_id.in_(user_ids),
            Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]),
        )
        .group_by(Ticket.user_id)
        .all()
    ):
        open_ticket_counts[row.user_id] = row.cnt

    # Bulk fetch sentiment logs per user
    all_logs = (
        db.query(SentimentLog)
        .filter(SentimentLog.employee_id.in_(user_ids))
        .all()
    )
    logs_by_user: Dict[str, List[SentimentLog]] = defaultdict(list)
    for log in all_logs:
        logs_by_user[str(log.employee_id)].append(log)

    # Bulk fetch message signals per user (topics + complaints)
    all_signals = (
        db.query(MessageSignal)
        .filter(MessageSignal.employee_id.in_(user_ids), MessageSignal.created_at >= now - timedelta(days=30))
        .all()
    )
    signals_by_user: Dict[str, List[MessageSignal]] = defaultdict(list)
    for sig in all_signals:
        signals_by_user[str(sig.employee_id)].append(sig)

    out: List[Dict[str, Any]] = []
    for u in users:
        uid = str(u.id)
        score_row = scores.get(u.id)
        risk_snapshot = risk_snaps.get(u.id)
        mh = mh_scores.get(u.id)

        # Sentiment
        if score_row:
            sentiment_pct = int(score_row.sentiment_score or 0)
        elif risk_snapshot and risk_snapshot.mood_score is not None:
            sentiment_pct = int(round(risk_snapshot.mood_score))
        else:
            sentiment_pct = 50

        # Risk
        if score_row:
            risk = int(score_row.risk_score or 0)
        elif risk_snapshot and risk_snapshot.attrition_risk is not None:
            risk = int(min(100, round(risk_snapshot.attrition_risk * 100)))
        else:
            risk = 0

        mental_health_score = int(score_row.mental_health_score) if score_row else (int(mh.score) if mh else None)

        last_ts = latest_msg_map.get(u.id) or u.updated_at
        days_inactive = max(0, int((now - last_ts).days)) if last_ts else 0
        open_n = open_ticket_counts.get(u.id, 0)

        user_logs = logs_by_user.get(uid, [])
        short_logs = [l for l in user_logs if l.created_at >= now - timedelta(days=7)]
        long_logs = [l for l in user_logs if l.created_at >= now - timedelta(days=60)]
        short_avg = round(sum(l.score for l in short_logs) / len(short_logs), 1) if short_logs else float(sentiment_pct)
        long_avg = round(sum(l.score for l in long_logs) / len(long_logs), 1) if long_logs else float(sentiment_pct)
        spike_alert = bool(long_avg - short_avg >= 15)

        latest_sentiment_at = max((l.created_at for l in user_logs), default=None)
        sentiment_sample_count_30d = len(long_logs)
        volume_confidence = min(1.0, sentiment_sample_count_30d / 8.0)
        if latest_sentiment_at:
            age_days = max(0.0, (now - latest_sentiment_at).total_seconds() / 86400.0)
            recency_confidence = 1.0 if age_days <= 1 else 0.8 if age_days <= 3 else 0.6 if age_days <= 7 else 0.4 if age_days <= 14 else 0.2
        else:
            recency_confidence = 0.2
        sentiment_confidence = round((0.65 * volume_confidence) + (0.35 * recency_confidence), 2)
        sentiment_confidence_band = "high" if sentiment_confidence >= 0.75 else "medium" if sentiment_confidence >= 0.45 else "low"

        # Emotions
        emotion_counts: Dict[str, int] = defaultdict(int)
        for l in user_logs:
            if l.created_at >= now - timedelta(days=30):
                emotion_counts[str(l.emotion or "neutral")] += 1
        top_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0] if emotion_counts else "neutral"

        # Topics
        user_signals = signals_by_user.get(uid, [])
        topic_counts: Dict[str, int] = defaultdict(int)
        for sig in user_signals:
            topic_counts[str(sig.topic or "general")] += 1
        top_topic = max(topic_counts.items(), key=lambda x: x[1])[0] if topic_counts else "general"

        complaints_5d = sum(1 for sig in user_signals if sig.created_at >= now - timedelta(days=5) and sig.severity in ("medium", "high"))
        negative_turns_in_window = sum(1 for l in user_logs if l.created_at >= sustained_start and l.label == "negative")
        sustained_risk_pattern = int(negative_turns_in_window) >= min_sustained
        silent_risk = bool(days_inactive >= 5 and sentiment_pct < 55)

        risk_explained = _explain_risk(getattr(score_row, "risk_factors", None) if score_row else None)
        dlabel = dept_name.get(str(u.department_id), "General") if u.department_id else "General"
        narrative = [
            f"Sentiment {'declining' if (score_row and score_row.trend_label == 'down') else 'stable'} ({int(long_avg)} -> {int(short_avg)})",
            f"{complaints_5d} complaint-like signals in last 5 days",
            f"Top topic: {top_topic.replace('_', ' ')}",
            f"{'Silent risk detected' if silent_risk else 'Engagement active'}",
        ]
        if sustained_risk_pattern:
            narrative.insert(0, f"Sustained negative pattern: {negative_turns_in_window} negative chat signals in last {sustained_wd} days")

        out.append(
            {
                "id": uid,
                "employee_id": u.employee_id or uid.replace("-", "")[:8].upper(),
                "name": u.name,
                "sentiment_score": sentiment_pct,
                "risk_score": risk,
                "last_active": _human_last_active(last_ts),
                "department": dlabel,
                "mental_health_score": mental_health_score,
                "risk_confidence": risk_explained["confidence"],
                "risk_calibration_band": risk_explained["band"],
                "risk_top_factors": risk_explained["top_factors"],
                "risk_factors": risk_explained["factors"],
                "trend": score_row.trend_label if score_row else "stable",
                "delta": int(score_row.trend_delta) if score_row else 0,
                "risk_label": "High" if risk >= 70 else ("Medium" if risk >= 40 else "Low"),
                "short_term_trend": short_avg,
                "long_term_trend": long_avg,
                "spike_alert": spike_alert,
                "top_topic": top_topic,
                "top_emotion": top_emotion,
                "sentiment_last_updated_at": latest_sentiment_at.isoformat() if latest_sentiment_at else None,
                "sentiment_confidence": sentiment_confidence,
                "sentiment_confidence_band": sentiment_confidence_band,
                "complaints_5d": int(complaints_5d),
                "silent_risk": silent_risk,
                "sustained_risk_pattern": sustained_risk_pattern,
                "negative_turns_in_window": int(negative_turns_in_window),
                "narrative": narrative,
            }
        )

    out.sort(key=lambda x: x["risk_score"], reverse=True)
    return out


def employee_insights_for_manager(db: Session, manager_id: UUID, limit: int = 50) -> List[Dict[str, Any]]:
    """Manager-scoped view of direct reports only."""
    limit = max(1, min(limit, 200))
    reports = (
        db.query(User.id)
        .filter(
            User.role == UserRole.employee,
            User.status == UserStatus.active,
            User.manager_id == manager_id,
        )
        .all()
    )
    report_id_set = {str(row[0]) for row in reports}
    if not report_id_set:
        return []

    all_insights = employee_insights_for_hr(db=db, limit=1000)
    filtered = [row for row in all_insights if row.get("id") in report_id_set]
    filtered.sort(key=lambda x: int(x.get("risk_score", 0)), reverse=True)
    return filtered[:limit]


def build_ai_summary(db: Session, open_tickets: int) -> str:
    """Actionable HR insight from real ticket + sentiment patterns (no LLM cost)."""
    from datetime import timedelta

    insights: list[str] = []
    open_statuses = [TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]
    open_rows = (
        db.query(Ticket.query, Ticket.category)
        .filter(Ticket.status.in_(open_statuses))
        .order_by(Ticket.created_at.desc())
        .limit(150)
        .all()
    )

    target_counts: Dict[str, int] = defaultdict(int)
    for query_text, category in open_rows:
        text = (query_text or "").strip()
        match = re.search(r"Against:\s*([^\n]+)", text, flags=re.IGNORECASE)
        target = (match.group(1).strip() if match else str(category or "").strip()) or "Unspecified"
        target_counts[target] += 1

    if target_counts:
        target, count = max(target_counts.items(), key=lambda item: item[1])
        if count >= 3:
            insights.append(f"{count} open tickets about {target} — recommend HR check-in.")

    activity_rows = (
        db.query(
            User.id,
            func.max(Message.created_at).label("last_message_at"),
        )
        .outerjoin(Conversation, Conversation.user_id == User.id)
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .filter(User.role == UserRole.employee, User.status == UserStatus.active)
        .group_by(User.id)
        .all()
    )
    cutoff = utcnow_naive() - timedelta(days=5)
    inactive_count = sum(1 for _, last_message_at in activity_rows if not last_message_at or last_message_at < cutoff)
    if inactive_count >= 3:
        insights.append(f"{inactive_count} employees inactive for 5+ days — trigger wellbeing scan.")

    manager_pattern = detect_manager_issue_pattern(db)
    if manager_pattern:
        insights.append(
            f"Pattern detected: {manager_pattern['count']} signals around manager issues in team {manager_pattern['manager']}."
        )

    if not insights:
        if open_tickets == 0:
            return "No open tickets right now — maintain weekly wellbeing reviews."
        return f"{open_tickets} open tickets with no dominant pattern yet — monitor trends daily."

    return " ".join(insights)


def detect_manager_issue_pattern(db: Session, days: int = 7) -> Optional[Dict[str, Any]]:
    since = utcnow_naive() - timedelta(days=max(1, min(days, 30)))
    rows = (
        db.query(User.manager_id, func.count(MessageSignal.id))
        .join(User, User.id == MessageSignal.employee_id)
        .filter(
            MessageSignal.created_at >= since,
            MessageSignal.topic == "manager_issue",
            User.manager_id.isnot(None),
        )
        .group_by(User.manager_id)
        .all()
    )
    if not rows:
        return None
    manager_id, count = max(rows, key=lambda x: int(x[1]))
    if int(count) < 3:
        return None
    manager = db.query(User).filter(User.id == manager_id).first()
    return {"manager_id": str(manager_id), "manager": manager.name if manager else "Unknown", "count": int(count)}


def compute_weekly_quality(db: Session, window_days: int = 7) -> Dict[str, Any]:
    """Weekly quality rollup: CSAT + first response latency."""
    window_days = max(1, min(window_days, 30))
    since = utcnow_naive() - timedelta(days=window_days)

    csat_rows = (
        db.query(ChatFeedback.rating)
        .filter(ChatFeedback.created_at >= since, ChatFeedback.source == "chat")
        .all()
    )
    ratings = [int(r[0]) for r in csat_rows if r and r[0] is not None]

    feedback_responses = len(ratings)
    avg_csat = round(sum(ratings) / feedback_responses, 2) if feedback_responses else 0.0
    helpful_count = sum(1 for r in ratings if r >= 4)
    detractor_count = sum(1 for r in ratings if r <= 2)
    helpful_rate = round(100.0 * helpful_count / feedback_responses, 1) if feedback_responses else 0.0
    detractor_rate = round(100.0 * detractor_count / feedback_responses, 1) if feedback_responses else 0.0

    latency_rows = (
        db.query(
            Conversation.id,
            func.min(case((Message.sender == MessageSender.user, Message.created_at), else_=None)).label("first_user"),
            func.min(case((Message.sender == MessageSender.bot, Message.created_at), else_=None)).label("first_bot"),
        )
        .join(Message, Message.conversation_id == Conversation.id)
        .filter(Conversation.started_at >= since)
        .group_by(Conversation.id)
        .all()
    )

    first_response_seconds: List[float] = []
    for _, first_user, first_bot in latency_rows:
        if not first_user or not first_bot:
            continue
        if first_bot < first_user:
            continue
        first_response_seconds.append((first_bot - first_user).total_seconds())

    avg_first_response_seconds = (
        round(sum(first_response_seconds) / len(first_response_seconds), 1)
        if first_response_seconds
        else 0.0
    )

    if feedback_responses == 0:
        quality_label = "Insufficient feedback"
    elif avg_csat >= 4.4 and helpful_rate >= 80:
        quality_label = "Excellent"
    elif avg_csat >= 3.6:
        quality_label = "Good"
    else:
        quality_label = "Needs attention"

    return {
        "window_days": window_days,
        "feedback_responses": feedback_responses,
        "avg_csat": avg_csat,
        "helpful_rate": helpful_rate,
        "detractor_rate": detractor_rate,
        "avg_first_response_seconds": avg_first_response_seconds,
        "conversations_measured": len(first_response_seconds),
        "quality_label": quality_label,
    }


def manager_effectiveness_for_hr(db: Session, limit: int = 50) -> List[Dict[str, Any]]:
    """Compute manager effectiveness from team sentiment, risk, engagement, and complaints."""
    limit = max(1, min(limit, 200))
    since = utcnow_naive() - timedelta(days=30)

    all_active_users = db.query(User).filter(User.status == UserStatus.active).all()
    all_active_employees = [u for u in all_active_users if u.role == UserRole.employee]
    manager_id_set = {str(u.manager_id) for u in all_active_employees if u.manager_id is not None}
    managers = [u for u in all_active_users if str(u.id) in manager_id_set]

    employee_rows = employee_insights_for_hr(db, limit=1000)
    employee_by_id = {row["id"]: row for row in employee_rows}

    results: List[Dict[str, Any]] = []
    for manager in managers:
        reports = [u for u in all_active_employees if u.manager_id is not None and str(u.manager_id) == str(manager.id)]
        if not reports:
            continue

        report_ids = [r.id for r in reports]
        report_insights = [employee_by_id.get(str(rid)) for rid in report_ids if employee_by_id.get(str(rid))]
        if report_insights:
            avg_sentiment = round(sum(int(r["sentiment_score"]) for r in report_insights) / len(report_insights), 1)
            avg_risk = round(sum(int(r["risk_score"]) for r in report_insights) / len(report_insights), 1)
        else:
            avg_sentiment = 50.0
            avg_risk = 0.0

        report_id_set = {str(rid) for rid in report_ids}
        open_complaints = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.category == "complaint",
                Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]),
            )
            .all()
        )
        # Robust matching across DB UUID adapters.
        if open_complaints:
            complaint_rows = (
                db.query(Ticket.user_id)
                .filter(
                    Ticket.category == "complaint",
                    Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]),
                )
                .all()
            )
            open_complaints = sum(1 for row in complaint_rows if str(row[0]) in report_id_set)
        else:
            open_complaints = 0

        activity_rows = (
            db.query(Conversation.user_id)
            .join(Message, Message.conversation_id == Conversation.id)
            .filter(Message.created_at >= since)
            .all()
        )
        active_reporters = len({str(row[0]) for row in activity_rows if str(row[0]) in report_id_set})
        engagement_ratio = active_reporters / max(len(report_ids), 1)

        effectiveness = (
            0.45 * avg_sentiment
            + 0.30 * (100.0 - avg_risk)
            + 0.20 * (engagement_ratio * 100.0)
            + 0.05 * max(0.0, 100.0 - min(100.0, open_complaints * 20.0))
        )
        effectiveness_score = round(max(0.0, min(100.0, effectiveness)), 1)
        if effectiveness_score >= 75:
            label = "strong"
        elif effectiveness_score >= 55:
            label = "steady"
        else:
            label = "needs_support"

        results.append(
            {
                "manager_id": str(manager.id),
                "manager_name": manager.name,
                "team_size": len(report_ids),
                "avg_sentiment_score": avg_sentiment,
                "avg_risk_score": avg_risk,
                "open_complaints": int(open_complaints),
                "engagement_ratio": round(engagement_ratio, 2),
                "effectiveness_score": effectiveness_score,
                "effectiveness_label": label,
            }
        )

    results.sort(key=lambda row: row["effectiveness_score"], reverse=True)
    return results[:limit]


def sentiment_analysis_source_drift(db: Session, *, days: int = 7) -> Dict[str, Any]:
    """
    Aggregate SentimentLog rows by analysis_source (llm / lexicon / hybrid / provided / unknown).
    Used for HR visibility into classifier mix and drift over time.
    """
    days = max(1, min(int(days), 90))
    since = utcnow_naive() - timedelta(days=days)
    try:
        rows = (
            db.query(SentimentLog.analysis_source, func.count(SentimentLog.id))
            .filter(SentimentLog.created_at >= since)
            .group_by(SentimentLog.analysis_source)
            .all()
        )
    except ProgrammingError:
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "window_days": days,
            "total": 0,
            "by_source": {},
            "pct_by_source": {},
        }
    by_source: Dict[str, int] = defaultdict(int)
    for src, cnt in rows:
        key = (src or "unknown").strip().lower() or "unknown"
        by_source[key] += int(cnt or 0)
    total = sum(by_source.values())
    pct_by_source = {k: round(100.0 * v / total, 1) for k, v in by_source.items()} if total else {}
    return {
        "window_days": days,
        "total": total,
        "by_source": dict(by_source),
        "pct_by_source": pct_by_source,
    }


def sentiment_source_drift_timeseries(db: Session, *, days: int = 14) -> List[Dict[str, Any]]:
    """Daily percentage mix of sentiment_logs.analysis_source (HR classifier drift over time)."""
    days = max(1, min(int(days), 90))
    start = utcnow_naive() - timedelta(days=days - 1)
    day_key = func.date(SentimentLog.created_at)
    src_label = func.lower(func.coalesce(SentimentLog.analysis_source, "unknown"))
    try:
        rows = (
            db.query(day_key, src_label, func.count(SentimentLog.id))
            .filter(SentimentLog.created_at >= start)
            .group_by(day_key, src_label)
            .all()
        )
    except ProgrammingError:
        try:
            db.rollback()
        except Exception:
            pass
        rows = []

    by_date: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for d, src, cnt in rows:
        if d is None:
            continue
        key = str(d)
        label = str(src or "unknown").strip().lower() or "unknown"
        by_date[key][label] += int(cnt or 0)

    out: List[Dict[str, Any]] = []
    for i in range(days):
        d = (utcnow_naive() - timedelta(days=days - 1 - i)).date()
        key = d.isoformat()
        bucket = dict(by_date.get(key, {}))
        total = sum(bucket.values())
        if total == 0:
            out.append({"date": key, "sources": {}})
            continue
        percentages = {
            src: round((count / total) * 100.0, 1)
            for src, count in sorted(bucket.items(), key=lambda item: item[1], reverse=True)
        }
        out.append({"date": key, "sources": percentages})
    return out


def sentiment_source_drift_timeseries_for_manager(
    db: Session, manager_id: UUID, *, days: int = 14
) -> List[Dict[str, Any]]:
    """Daily classifier-path mix for direct reports only (manager dashboard)."""
    days = max(1, min(int(days), 90))
    start = utcnow_naive() - timedelta(days=days - 1)
    day_key = func.date(SentimentLog.created_at)
    src_label = func.lower(func.coalesce(SentimentLog.analysis_source, "unknown"))
    try:
        rows = (
            db.query(day_key, src_label, func.count(SentimentLog.id))
            .join(User, User.id == SentimentLog.employee_id)
            .filter(
                SentimentLog.created_at >= start,
                User.manager_id == manager_id,
                User.role == UserRole.employee,
                User.status == UserStatus.active,
            )
            .group_by(day_key, src_label)
            .all()
        )
    except ProgrammingError:
        try:
            db.rollback()
        except Exception:
            pass
        rows = []

    by_date: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for d, src, cnt in rows:
        if d is None:
            continue
        key = str(d)
        label = str(src or "unknown").strip().lower() or "unknown"
        by_date[key][label] += int(cnt or 0)

    out: List[Dict[str, Any]] = []
    for i in range(days):
        d = (utcnow_naive() - timedelta(days=days - 1 - i)).date()
        key = d.isoformat()
        bucket = dict(by_date.get(key, {}))
        total = sum(bucket.values())
        if total == 0:
            out.append({"date": key, "sources": {}})
            continue
        percentages = {
            src: round((count / total) * 100.0, 1)
            for src, count in sorted(bucket.items(), key=lambda item: item[1], reverse=True)
        }
        out.append({"date": key, "sources": percentages})
    return out
