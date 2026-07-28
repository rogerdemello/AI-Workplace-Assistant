"""Retention deletes what it should, and nothing at all by default.

Deletion here is irreversible and lands on employee disclosures, so the
defaults matter as much as the mechanism: a deployment that never configures
retention must never lose data, and a misconfigured one must not quietly take
more than it was told to.
"""

from datetime import timedelta

from app.config import Settings, settings
from app.core.time import utcnow_naive
from app.models.conversation import Conversation, Message, MessageSender
from scripts.apply_retention import _policies


def _message(db, user_id, age_days: int, text="something personal"):
    conversation = Conversation(user_id=user_id)
    db.add(conversation)
    db.flush()
    msg = Message(
        conversation_id=conversation.id,
        sender=MessageSender.user,
        message_text=text,
        created_at=utcnow_naive() - timedelta(days=age_days),
    )
    db.add(msg)
    db.commit()
    return msg


def test_every_retention_period_defaults_to_keep_forever():
    """Nobody should inherit a deletion policy from a config file."""
    defaults = Settings()
    for name in (
        "RETENTION_CHAT_MESSAGES_DAYS",
        "RETENTION_SENTIMENT_LOGS_DAYS",
        "RETENTION_AUDIT_LOGS_DAYS",
        "RETENTION_ANONYMOUS_FEEDBACK_DAYS",
    ):
        assert getattr(defaults, name) == 0, f"{name} must default to keep-forever"


def test_no_policies_are_active_by_default(monkeypatch):
    for name, _model, _col, _days in _policies():
        pass
    active = [p for p in _policies() if p[3] and p[3] > 0]
    assert active == [], "a retention rule is active with default settings"


def test_configured_period_selects_only_older_rows(db, test_user, monkeypatch):
    monkeypatch.setattr(settings, "RETENTION_CHAT_MESSAGES_DAYS", 30)
    old = _message(db, test_user.id, age_days=60)
    recent = _message(db, test_user.id, age_days=5)

    label, model, column, days = next(p for p in _policies() if p[0] == "chat messages")
    cutoff = utcnow_naive() - timedelta(days=days)
    doomed = {m.id for m in db.query(model).filter(column < cutoff).all()}

    assert old.id in doomed
    assert recent.id not in doomed, "retention would delete a message inside the window"


def test_deleting_chat_text_leaves_derived_scores_intact(db, test_user, monkeypatch):
    """The point of the policy: keep the trend, drop the words."""
    from app.models.employee_score import EmployeeScore
    from app.services.sentiment_pipeline import SentimentPipelineService

    monkeypatch.setattr(settings, "RETENTION_CHAT_MESSAGES_DAYS", 30)
    old = _message(db, test_user.id, age_days=60)
    SentimentPipelineService(db).process_message(
        employee_id=test_user.id,
        message_id=old.id,
        message_text=old.message_text,
        sentiment_label="negative",
        sentiment_score=-0.5,
    )
    score_before = db.query(EmployeeScore).filter(
        EmployeeScore.employee_id == test_user.id
    ).one().sentiment_score

    _label, model, column, days = next(p for p in _policies() if p[0] == "chat messages")
    db.query(model).filter(column < utcnow_naive() - timedelta(days=days)).delete(
        synchronize_session=False
    )
    db.commit()

    score_after = db.query(EmployeeScore).filter(
        EmployeeScore.employee_id == test_user.id
    ).one().sentiment_score
    assert score_after == score_before
