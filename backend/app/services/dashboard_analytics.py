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
from sqlalchemy.orm import Session
from sqlalchemy.types import Date

from ..models.conversation import Conversation, Message, MessageSender, SentimentLabel
from ..core.time import utcnow_naive
from ..models.analytics import MentalHealthScore
from ..models.chat_feedback import ChatFeedback
from ..models.department import Department
from ..models.risk_snapshot import RiskSnapshot
from ..models.survey import SurveyResponse
from ..models.ticket import Ticket, TicketStatus
from ..models.user import User, UserRole, UserStatus


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


def sentiment_trend_days(db: Session, days: int = 14) -> List[Dict[str, Any]]:
    days = max(1, min(days, 90))
    start = utcnow_naive() - timedelta(days=days - 1)
    day_key = cast(Message.created_at, Date)

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
    """Employees + sentiment/risk derived from messages and tickets."""
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

    out: List[Dict[str, Any]] = []
    for u in users:
        last_msg = (
            db.query(func.max(Message.created_at))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == u.id)
            .scalar()
        )

        sentiments = (
            db.query(Message.sentiment)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == u.id, Message.sender == MessageSender.user, Message.sentiment.isnot(None))
            .order_by(Message.created_at.desc())
            .limit(10)
            .all()
        )
        pos = sum(1 for s in sentiments if s[0] == SentimentLabel.positive)
        neg = sum(1 for s in sentiments if s[0] == SentimentLabel.negative)
        neu = sum(1 for s in sentiments if s[0] == SentimentLabel.neutral)
        total_s = len(sentiments)
        if total_s == 0:
            negative_sentiment_pct = 0.0
            snapshot = (
                db.query(RiskSnapshot)
                .filter(RiskSnapshot.user_id == u.id)
                .order_by(RiskSnapshot.created_at.desc())
                .first()
            )
            if snapshot and snapshot.mood_score is not None:
                sentiment_pct = int(round(snapshot.mood_score))
            else:
                sentiment_pct = 0
        else:
            negative_sentiment_pct = (neg / max(total_s, 1)) * 100.0
            sentiment_pct = int(round(((pos + 0.5 * neu) / max(total_s, 1)) * 100))

        open_n = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.user_id == u.id,
                Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]),
            )
            .scalar()
            or 0
        )
        last_ts = last_msg or u.updated_at
        days_inactive = max(0, int((utcnow_naive() - last_ts).days)) if last_ts else 0

        risk_snapshot = (
            db.query(RiskSnapshot)
            .filter(RiskSnapshot.user_id == u.id)
            .order_by(RiskSnapshot.created_at.desc())
            .first()
        )
        if risk_snapshot and risk_snapshot.attrition_risk is not None:
            risk = int(min(100, round(risk_snapshot.attrition_risk * 100)))
        else:
            risk = 0

        mh = (
            db.query(MentalHealthScore)
            .filter(MentalHealthScore.user_id == u.id)
            .order_by(MentalHealthScore.created_at.desc())
            .first()
        )
        mental_health_score = int(mh.score) if mh else None

        dlabel = dept_name.get(str(u.department_id), "General") if u.department_id else "General"

        out.append(
            {
                "id": str(u.id),
                "employee_id": u.employee_id or str(u.id).replace("-", "")[:8].upper(),
                "name": u.name,
                "sentiment_score": sentiment_pct,
                "risk_score": risk,
                "last_active": _human_last_active(last_ts),
                "department": dlabel,
                "mental_health_score": mental_health_score,
            }
        )

    out.sort(key=lambda x: x["risk_score"], reverse=True)
    return out


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

    if not insights:
        if open_tickets == 0:
            return "No open tickets right now — maintain weekly wellbeing reviews."
        return f"{open_tickets} open tickets with no dominant pattern yet — monitor trends daily."

    return " ".join(insights)


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
