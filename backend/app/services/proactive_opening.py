"""Server-driven first message for employee chat, tuned by recent sentiment aggregates."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from ..config import settings
from ..core.time import utcnow_naive
from ..models.conversation import Conversation, Message, MessageSender, SentimentLabel
from ..models.employee_score import EmployeeScore
from ..models.personal_fact import PersonalFact, PersonalFactType
from ..models.user import User
from .hr_personality import (
    DAILY_CHECKIN_OPENERS,
    FIRST_TIME_OPENERS,
    WIND_DOWN_OPENERS,
    get_conversation_starter,
)
from .memory_service import get_memory_service


_FACT_REFERENCE_PROBABILITY = 0.3
_FACT_RECENCY_DAYS = 30

_MEMORY_REFERENCE_PROBABILITY = 0.4
# Tags we never reference in a light greeting — surfacing distress unprompted
# reads as surveillance, not care.
_MEMORY_SENSITIVE_TAGS = {
    "stress", "burnout", "complaint", "anxiety", "depressed", "harassment",
    "conflict", "resignation", "grievance",
}


@dataclass
class ProactiveOpening:
    """Greeting plus UI hints for how the client should frame it."""

    text: str
    suggested_mood_checkin: bool = False


def _display_tz() -> timezone | ZoneInfo:
    try:
        return ZoneInfo(settings.DEFAULT_DISPLAY_TIMEZONE or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def _local_now() -> datetime:
    """Current time in the configured display timezone (tz-aware)."""
    return datetime.now(timezone.utc).astimezone(_display_tz())


def _local_midnight_utc_naive() -> datetime:
    """Start of 'today' in local tz, expressed as naive-UTC for DB comparison.

    Conversation.started_at is stored as naive UTC, so we convert the local
    midnight boundary back to naive UTC before querying.
    """
    local = _local_now()
    local_midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(timezone.utc).replace(tzinfo=None)


def _first_name(user: User) -> str:
    raw = (user.name or "").strip()
    if not raw:
        return "there"
    return raw.split()[0]


def _tone_from_employee_score(row: EmployeeScore | None) -> str:
    if row is None:
        return "neutral"
    s = int(row.sentiment_score or 50)
    if s < 42:
        return "negative"
    if s > 58:
        return "positive"
    return "neutral"


def _tone_from_last_user_message(db: Session, user_id: UUID) -> str | None:
    last = (
        db.query(Message.sentiment)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Conversation.user_id == user_id,
            Message.sender == MessageSender.user,
            Message.sentiment.isnot(None),
        )
        .order_by(Message.created_at.desc())
        .limit(1)
        .scalar()
    )
    if last is None:
        return None
    if last == SentimentLabel.negative:
        return "negative"
    if last == SentimentLabel.positive:
        return "positive"
    return "neutral"


def _is_first_time(db: Session, user_id: UUID) -> bool:
    """True when the user has no conversations yet.

    IMPORTANT: call this BEFORE creating the new conversation row, or it will
    always see the just-created row and report False.
    """
    return (
        db.query(Conversation.id)
        .filter(Conversation.user_id == user_id)
        .limit(1)
        .first()
    ) is None


def _has_conversation_today(db: Session, user_id: UUID) -> bool:
    """Whether the user already started a conversation today (local tz)."""
    since = _local_midnight_utc_naive()
    return (
        db.query(Conversation.id)
        .filter(
            Conversation.user_id == user_id,
            Conversation.started_at >= since,
        )
        .limit(1)
        .first()
    ) is not None


def _recent_fact_reference(db: Session, user_id: UUID) -> str | None:
    """Pick a recent, light personal fact we can naturally weave into a greeting.

    Returns None most of the time so the greeting doesn't feel surveillance-y.
    Only hobbies + family_notes are used — birthdays/anniversaries deserve
    their own dedicated greeting flow.
    """
    cutoff = utcnow_naive() - timedelta(days=_FACT_RECENCY_DAYS)
    candidates = (
        db.query(PersonalFact)
        .filter(
            PersonalFact.user_id == user_id,
            PersonalFact.fact_type.in_([PersonalFactType.hobby, PersonalFactType.family_note]),
            PersonalFact.created_at >= cutoff,
        )
        .order_by(PersonalFact.created_at.desc())
        .limit(5)
        .all()
    )
    if not candidates:
        return None
    if random.random() > _FACT_REFERENCE_PROBABILITY:
        return None
    fact = random.choice(candidates)
    value = (fact.fact_value or "").strip()
    if not value:
        return None
    if fact.fact_type == PersonalFactType.hobby:
        return f"how's the {value} going?"
    return f"how are things with {value}?"


def _recent_memory_reference(db: Session, user_id: UUID) -> str | None:
    """Reference the last conversation's summary, subtly and only when light.

    Fires ~40% of the time, skips anything tagged as distress, and never more
    than once per opening (the caller enforces a single memory hook total).
    """
    if random.random() > _MEMORY_REFERENCE_PROBABILITY:
        return None
    try:
        recent = get_memory_service(db).retrieve_memory(user_id=user_id, limit=1)
    except Exception:
        return None
    if not recent:
        return None
    item = recent[0]
    summary = (item.summary or "").strip()
    if not summary:
        return None
    tags = {str(t).strip().lower() for t in (item.tags or [])}
    if tags & _MEMORY_SENSITIVE_TAGS:
        return None
    # Keep it short — a long quoted summary feels clinical.
    snippet = summary if len(summary) <= 90 else summary[:87].rstrip() + "…"
    return f"last time we talked about {snippet} — how's that going?"


def build_proactive_chat_opening(db: Session, user: User) -> ProactiveOpening:
    """
    Opening line when MARK starts the thread (no synthetic user message).

    Branches on first-time / first-chat-of-day / returning + recent tone, and
    occasionally references a known personal fact or the last conversation so
    the greeting feels personal. Returns the text plus UI hints.

    Call this BEFORE creating the day's conversation row so the daily-ritual
    detection is accurate.
    """
    fn = _first_name(user)

    if _is_first_time(db, user.id):
        body = random.choice(FIRST_TIME_OPENERS)
        if fn.lower() != "there":
            body = body.replace("Hey!", f"Hey {fn}!", 1).replace("Hi there!", f"Hi {fn}!", 1)
        return ProactiveOpening(text=body, suggested_mood_checkin=True)

    row = db.query(EmployeeScore).filter(EmployeeScore.employee_id == user.id).first()
    tone = _tone_from_last_user_message(db, user.id) or _tone_from_employee_score(row)

    # First chat of the day → a warm check-in (morning) or wind-down (evening).
    if not _has_conversation_today(db, user.id):
        evening = _local_now().hour >= int(settings.WIND_DOWN_HOUR)
        body = random.choice(WIND_DOWN_OPENERS if evening else DAILY_CHECKIN_OPENERS)
        if fn.lower() != "there":
            body = f"Hey {fn} — {body[0].lower()}{body[1:]}"
        return ProactiveOpening(text=body, suggested_mood_checkin=True)

    mode = "support" if tone == "negative" else "assistant"
    body = get_conversation_starter(sentiment=tone, mode=mode)

    # At most one personal hook per opening, and never when tone is negative.
    hook = None
    if tone != "negative":
        hook = _recent_memory_reference(db, user.id) or _recent_fact_reference(db, user.id)
    if hook:
        body = f"{body} Also — {hook}"

    if fn.lower() != "there":
        return ProactiveOpening(text=f"Hey {fn} — {body}")
    return ProactiveOpening(text=body)
