"""Server-driven first message for employee chat, tuned by recent sentiment aggregates."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ..models.conversation import Conversation, Message, MessageSender, SentimentLabel
from ..models.employee_score import EmployeeScore
from ..models.user import User
from .hr_personality import get_conversation_starter


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


def build_proactive_chat_opening(db: Session, user: User) -> str:
    """
    Opening line when MARK starts the thread (no synthetic user message).
    Uses last chat tone if available, else rolling employee_scores sentiment.
    """
    row = db.query(EmployeeScore).filter(EmployeeScore.employee_id == user.id).first()
    tone = _tone_from_last_user_message(db, user.id) or _tone_from_employee_score(row)
    mode = "support" if tone == "negative" else "assistant"
    body = get_conversation_starter(sentiment=tone, mode=mode)
    fn = _first_name(user)
    if fn.lower() != "there":
        return f"Hey {fn} — {body}"
    return body
