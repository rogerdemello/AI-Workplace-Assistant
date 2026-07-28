"""Reprocessing must repair gaps without corrupting what is already there.

The pipeline is best-effort: when it fails the chat reply still succeeds and the
message is saved, but the signal never reaches HR. The employee's message
exists; the fact that they were struggling does not. These tests cover the two
halves of fixing that — finding the gap, and being safe to run repeatedly.
"""

from datetime import timedelta

from app.core.time import utcnow_naive
from app.models.conversation import Conversation, Message, MessageSender
from app.models.sentiment_log import SentimentLog
from app.services.sentiment_pipeline import SentimentPipelineService
from scripts.reconcile_sentiment import find_unprocessed


def _conversation_with_message(db, user_id, text="the reorg has been rough", age_days=0):
    conversation = Conversation(user_id=user_id)
    db.add(conversation)
    db.flush()
    message = Message(
        conversation_id=conversation.id,
        sender=MessageSender.user,
        message_text=text,
        created_at=utcnow_naive() - timedelta(days=age_days),
    )
    db.add(message)
    db.commit()
    return conversation, message


def test_reprocessing_a_message_does_not_duplicate_its_log(db, test_user):
    """Without this, every reconcile run would skew the employee's score."""
    _conv, message = _conversation_with_message(db, test_user.id)
    pipeline = SentimentPipelineService(db)

    for _ in range(3):
        pipeline.process_message(
            employee_id=test_user.id,
            message_id=message.id,
            message_text=message.message_text,
            sentiment_label="negative",
            sentiment_score=-0.6,
        )

    logs = db.query(SentimentLog).filter(SentimentLog.message_id == message.id).all()
    assert len(logs) == 1, f"reprocessing created {len(logs)} logs"


def test_unprocessed_messages_are_found(db, test_user):
    _conv, message = _conversation_with_message(db, test_user.id)

    pending = find_unprocessed(db, days=7, limit=100)
    assert message.id in [m.id for m, _ in pending]


def test_already_processed_messages_are_not_reprocessed(db, test_user):
    _conv, message = _conversation_with_message(db, test_user.id)
    SentimentPipelineService(db).process_message(
        employee_id=test_user.id,
        message_id=message.id,
        message_text=message.message_text,
        sentiment_label="neutral",
        sentiment_score=0.0,
    )

    pending = find_unprocessed(db, days=7, limit=100)
    assert message.id not in [m.id for m, _ in pending]


def test_messages_outside_the_window_are_left_alone(db, test_user):
    _conv, old = _conversation_with_message(db, test_user.id, age_days=30)

    pending = find_unprocessed(db, days=7, limit=100)
    assert old.id not in [m.id for m, _ in pending]


def test_bot_messages_are_not_candidates(db, test_user):
    """Only what the employee said carries a signal worth scoring."""
    conversation = Conversation(user_id=test_user.id)
    db.add(conversation)
    db.flush()
    bot = Message(
        conversation_id=conversation.id,
        sender=MessageSender.bot,
        message_text="How are things going?",
    )
    db.add(bot)
    db.commit()

    pending = find_unprocessed(db, days=7, limit=100)
    assert bot.id not in [m.id for m, _ in pending]


def test_reconcile_repairs_a_gap_end_to_end(db, test_user):
    _conv, message = _conversation_with_message(db, test_user.id)
    assert db.query(SentimentLog).filter(SentimentLog.message_id == message.id).count() == 0

    pending = find_unprocessed(db, days=7, limit=100)
    pipeline = SentimentPipelineService(db)
    for msg, employee_id in pending:
        pipeline.process_message(
            employee_id=employee_id,
            message_id=msg.id,
            message_text=msg.message_text or "",
            sentiment_label="negative",
            sentiment_score=-0.5,
        )

    assert db.query(SentimentLog).filter(SentimentLog.message_id == message.id).count() == 1
    assert find_unprocessed(db, days=7, limit=100) == []
