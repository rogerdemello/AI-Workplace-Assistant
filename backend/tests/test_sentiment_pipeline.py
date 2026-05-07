import uuid


def test_sentiment_pipeline_logs_message_and_updates_employee_score(db, test_user):
    from app.models.conversation import MessageSender
    from app.models.message_signal import MessageSignal
    from app.services.chat import ChatService
    from app.services.sentiment_pipeline import SentimentPipelineService

    chat = ChatService(db)
    conv = chat.create_conversation(test_user.id)
    msg = chat.add_message(
        conversation_id=conv.id,
        message_text="I feel frustrated because my manager ignores my work",
        sender=MessageSender.user,  # schema enum is accepted by .value
        sentiment="negative",
    )

    result = SentimentPipelineService(db).process_message(
        employee_id=test_user.id,
        message_id=msg.id,
        message_text=msg.message_text,
        sentiment_label="negative",
        sentiment_score=-0.7,
    )

    assert result["label"] == "negative"
    assert result["score"] <= 35
    assert result["emotion"] in {"frustration", "anger"}
    assert result["topic"] == "manager_issue"
    assert result["severity"] == "high"
    assert result["employee_score"]["sentiment_score"] <= 40
    sig = db.query(MessageSignal).filter(MessageSignal.message_id == msg.id).first()
    assert sig is not None
    assert sig.topic == "manager_issue"
    from app.models.sentiment_log import SentimentLog

    slog = db.query(SentimentLog).filter(SentimentLog.message_id == msg.id).first()
    assert slog is not None
    assert slog.analysis_source == "provided"


def test_dashboard_employee_insights_uses_employee_scores(db):
    from app.models.employee_score import EmployeeScore
    from app.models.sentiment_log import SentimentLog
    from app.models.user import User, UserRole, UserStatus
    from app.auth import hash_password
    from app.services.dashboard_analytics import employee_insights_for_hr

    employee = User(
        id=uuid.uuid4(),
        email="sentiment-employee@example.com",
        name="Priya Sharma",
        hashed_password=hash_password("pass123"),
        role=UserRole.employee,
        status=UserStatus.active,
    )
    db.add(employee)
    db.commit()

    score = EmployeeScore(
        employee_id=employee.id,
        sentiment_score=42,
        engagement_score=64,
        risk_score=74,
        mental_health_score=39,
        trend_delta=-23,
        trend_label="down",
    )
    db.add(score)
    db.add(
        SentimentLog(
            employee_id=employee.id,
            message_id=uuid.uuid4(),
            score=34,
            label="negative",
            emotion="stress",
        )
    )
    db.commit()

    rows = employee_insights_for_hr(db, limit=100)
    match = next((r for r in rows if r["id"] == str(employee.id)), None)
    assert match is not None
    assert match["sentiment_score"] == 42
    assert match["trend"] == "down"
    assert match["delta"] == -23
    assert match["risk_label"] == "High"
    assert match["top_emotion"] == "stress"
    assert match["sentiment_last_updated_at"] is not None
    assert match["sentiment_confidence"] is not None
    assert 0.0 <= float(match["sentiment_confidence"]) <= 1.0
    assert match["sentiment_confidence_band"] in {"low", "medium", "high"}
    assert match["sustained_risk_pattern"] is False
    assert match["negative_turns_in_window"] == 1
    assert "narrative" in match


def test_sentiment_pipeline_dampens_single_message_sentiment_spike(db, test_user):
    from app.models.conversation import MessageSender
    from app.models.employee_score import EmployeeScore
    from app.services.chat import ChatService
    from app.services.sentiment_pipeline import SentimentPipelineService

    db.add(
        EmployeeScore(
            employee_id=test_user.id,
            sentiment_score=70,
            engagement_score=60,
            risk_score=30,
            mental_health_score=65,
            trend_delta=0,
            trend_label="stable",
        )
    )
    db.commit()

    chat = ChatService(db)
    conv = chat.create_conversation(test_user.id)
    msg = chat.add_message(
        conversation_id=conv.id,
        message_text="I am completely overwhelmed and burned out today",
        sender=MessageSender.user,
        sentiment="negative",
    )

    result = SentimentPipelineService(db).process_message(
        employee_id=test_user.id,
        message_id=msg.id,
        message_text=msg.message_text,
        sentiment_label="negative",
        sentiment_score=-0.95,
    )

    # Guardrail limits abrupt one-turn drops (70 -> >=60 with max_step=10).
    assert result["employee_score"]["sentiment_score"] >= 60


def test_sustained_negative_pattern_creates_hr_notification(db, test_user):
    from app.models.conversation import MessageSender
    from app.models.hr_notification import HrNotification
    from app.services.chat import ChatService
    from app.services.sentiment_pipeline import SentimentPipelineService
    from app.services.sustained_risk_alerts import SUSTAINED_NOTIFICATION_TYPE

    chat = ChatService(db)
    conv = chat.create_conversation(test_user.id)
    pipeline = SentimentPipelineService(db)

    def add_neg(text: str):
        msg = chat.add_message(
            conversation_id=conv.id,
            message_text=text,
            sender=MessageSender.user,
            sentiment="negative",
        )
        pipeline.process_message(
            employee_id=test_user.id,
            message_id=msg.id,
            message_text=msg.message_text,
            sentiment_label="negative",
            sentiment_score=-0.6,
        )

    add_neg("I am frustrated with workload")
    add_neg("Still overwhelmed and upset")
    assert (
        db.query(HrNotification)
        .filter(
            HrNotification.actor_id == test_user.id,
            HrNotification.notification_type == SUSTAINED_NOTIFICATION_TYPE,
        )
        .count()
        == 0
    )

    add_neg("This is the third negative signal in the window")
    count = (
        db.query(HrNotification)
        .filter(
            HrNotification.actor_id == test_user.id,
            HrNotification.notification_type == SUSTAINED_NOTIFICATION_TYPE,
        )
        .count()
    )
    assert count == 1

    add_neg("Fourth negative — should not duplicate within cooldown")
    assert (
        db.query(HrNotification)
        .filter(
            HrNotification.actor_id == test_user.id,
            HrNotification.notification_type == SUSTAINED_NOTIFICATION_TYPE,
        )
        .count()
        == 1
    )
