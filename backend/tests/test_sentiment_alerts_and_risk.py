"""Tests for sentiment alerts and conversation risk scoring."""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from app.services.sentiment_alerts import SentimentAlertService
from app.services.conversation_risk_scorer import ConversationRiskScorer
from app.models.sentiment_log import SentimentLog
from app.models.hr_notification import HrNotification
from app.models.conversation import Conversation


class TestSentimentAlerts:
    """Test real-time sentiment alert system."""

    @pytest.fixture
    def alert_service(self, db):
        return SentimentAlertService(db)

    def test_low_sentiment_creates_alert(self, db, test_user, alert_service):
        """Alert should be created when sentiment drops below threshold."""
        alerts = alert_service.process_message_sentiment(
            employee_id=test_user.id,
            message_id=uuid4(),
            sentiment_score=25,
            sentiment_label="negative",
            emotion="frustration",
        )
        
        assert len(alerts) >= 1
        
        # Verify in DB
        notifications = db.query(HrNotification).filter(
            HrNotification.actor_id == test_user.id,
        ).all()
        
        assert len(notifications) >= 1
        assert any("sentiment_threshold" in n.notification_type for n in notifications)

    def test_emotion_alert(self, db, test_user, alert_service):
        """Alert should be created for critical emotions."""
        alerts = alert_service.process_message_sentiment(
            employee_id=test_user.id,
            message_id=uuid4(),
            sentiment_score=45,
            sentiment_label="negative",
            emotion="burnout",
        )
        
        assert len(alerts) >= 1
        
        # Check for emotion alert
        notifications = db.query(HrNotification).filter(
            HrNotification.actor_id == test_user.id,
            HrNotification.notification_type.like("%emotion%"),
        ).all()
        
        assert len(notifications) >= 1

    def test_cooldown_prevents_duplicate_alerts(self, db, test_user, alert_service):
        """Same alert type should not fire within cooldown period."""
        # First alert
        alerts1 = alert_service.process_message_sentiment(
            employee_id=test_user.id,
            message_id=uuid4(),
            sentiment_score=20,
            sentiment_label="negative",
        )
        assert len(alerts1) >= 1
        
        # Second alert immediately - should be blocked by cooldown
        alerts2 = alert_service.process_message_sentiment(
            employee_id=test_user.id,
            message_id=uuid4(),
            sentiment_score=15,
            sentiment_label="negative",
        )
        
        # Should not create new alert due to cooldown
        assert len(alerts2) == 0

    def test_sustained_negative_alert(self, db, test_user, alert_service):
        """Alert for sustained negative sentiment pattern."""
        # Create multiple negative sentiments
        for i in range(3):
            log = SentimentLog(
                employee_id=test_user.id,
                message_id=uuid4(),
                score=20,
                label="negative",
                emotion="frustration",
                created_at=datetime.utcnow() - timedelta(hours=i),
            )
            db.add(log)
        db.commit()
        
        alerts = alert_service.process_message_sentiment(
            employee_id=test_user.id,
            message_id=uuid4(),
            sentiment_score=20,
            sentiment_label="negative",
        )
        
        # Should trigger sustained negative alert
        from app.models.hr_notification import HrNotification
        notifs = db.query(HrNotification).filter(
            HrNotification.actor_id == test_user.id,
            HrNotification.notification_type == "sentiment_alert:sustained_negative",
        ).all()
        assert len(notifs) >= 1

    def test_conversation_risk_alert(self, db, test_user, alert_service):
        """Alert for high conversation risk."""
        from app.models.conversation import Conversation
        
        # Create conversation record
        conv = Conversation(user_id=test_user.id, status="active")
        db.add(conv)
        db.commit()
        
        # Create conversation with multiple negative sentiments
        for i in range(5):
            log = SentimentLog(
                employee_id=test_user.id,
                message_id=uuid4(),
                conversation_id=conv.id,
                score=15,
                label="negative",
                emotion="anxiety",
            )
            db.add(log)
        db.commit()
        
        alerts = alert_service.process_message_sentiment(
            employee_id=test_user.id,
            message_id=uuid4(),
            sentiment_score=15,
            sentiment_label="negative",
            conversation_id=conv.id,
        )
        
        # Should trigger conversation risk alert
        notifs = db.query(HrNotification).filter(
            HrNotification.actor_id == test_user.id,
            HrNotification.notification_type == "sentiment_alert:conversation_risk",
        ).all()
        assert len(notifs) >= 1

    def test_get_active_alerts(self, db, test_user, alert_service):
        """Retrieve active alerts."""
        alert_service.process_message_sentiment(
            employee_id=test_user.id,
            message_id=uuid4(),
            sentiment_score=20,
            sentiment_label="negative",
        )
        
        active = alert_service.get_active_alerts(hours=1)
        assert len(active) >= 1
        assert active[0]["employee_id"] == str(test_user.id)

    def test_dismiss_alert(self, db, test_user, alert_service):
        """Dismiss an alert."""
        alerts = alert_service.process_message_sentiment(
            employee_id=test_user.id,
            message_id=uuid4(),
            sentiment_score=20,
            sentiment_label="negative",
        )
        
        assert len(alerts) >= 1
        alert_id = alerts[0]
        
        success = alert_service.dismiss_alert(alert_id)
        assert success is True
        
        # Verify dismissed
        from uuid import UUID as UUIDType
        alert_uuid = UUIDType(alert_id)
        notification = db.query(HrNotification).filter(
            HrNotification.id == alert_uuid,
        ).first()
        assert notification.severity == "dismissed"


class TestConversationRiskScorer:
    """Test conversation-level risk scoring."""

    @pytest.fixture
    def risk_scorer(self, db):
        return ConversationRiskScorer(db)

    def test_score_low_risk_conversation(self, db, test_user, risk_scorer):
        """Low risk conversation should have low score."""
        conversation_id = uuid4()
        
        # Create positive sentiment logs
        for i in range(3):
            log = SentimentLog(
                employee_id=test_user.id,
                message_id=uuid4(),
                conversation_id=conversation_id,
                score=75,
                label="positive",
                emotion="satisfaction",
            )
            db.add(log)
        db.commit()
        
        metrics = risk_scorer.score_conversation(conversation_id)
        assert metrics is not None
        assert metrics.risk_score < 30
        assert metrics.alert_level == "none"
        assert metrics.requires_hr_attention is False

    def test_score_high_risk_conversation(self, db, test_user, risk_scorer):
        """High risk conversation should have high score."""
        conversation_id = uuid4()
        
        # Create negative sentiment logs with declining trend
        scores = [50, 40, 30, 20, 10]
        for score in scores:
            log = SentimentLog(
                employee_id=test_user.id,
                message_id=uuid4(),
                conversation_id=conversation_id,
                score=score,
                label="negative",
                emotion="frustration",
            )
            db.add(log)
        db.commit()
        
        metrics = risk_scorer.score_conversation(conversation_id)
        assert metrics is not None
        assert metrics.risk_score >= 70
        assert metrics.alert_level in ["high", "critical"]
        assert metrics.requires_hr_attention is True
        assert metrics.sentiment_trend == "declining"

    def test_score_conversation_with_burnout(self, db, test_user, risk_scorer):
        """Conversation with burnout emotion should be high risk."""
        conversation_id = uuid4()
        
        log = SentimentLog(
            employee_id=test_user.id,
            message_id=uuid4(),
            conversation_id=conversation_id,
            score=30,
            label="negative",
            emotion="burnout",
        )
        db.add(log)
        db.commit()
        
        metrics = risk_scorer.score_conversation(conversation_id)
        assert metrics is not None
        assert "burnout" in metrics.emotions_detected
        assert metrics.risk_score >= 50  # Critical emotion adds significant risk

    def test_get_high_risk_conversations(self, db, test_user, risk_scorer):
        """Retrieve high-risk conversations."""
        # Create a conversation record first
        from app.models.conversation import Conversation
        conversation = Conversation(
            user_id=test_user.id,
            status="active",
        )
        db.add(conversation)
        db.commit()
        
        # Create sentiment logs for the conversation
        for i in range(5):
            log = SentimentLog(
                employee_id=test_user.id,
                message_id=uuid4(),
                conversation_id=conversation.id,
                score=20,
                label="negative",
                emotion="anxiety",
            )
            db.add(log)
        db.commit()
        
        high_risk = risk_scorer.get_high_risk_conversations(min_risk=70)
        assert len(high_risk) >= 1
        assert any(str(c.conversation_id) == str(conversation.id) for c in high_risk)

    def test_employee_risk_summary(self, db, test_user, risk_scorer):
        """Get aggregated risk summary for employee."""
        from app.models.conversation import Conversation
        
        # Create multiple conversations with records
        for conv_num in range(2):
            conv = Conversation(
                user_id=test_user.id,
                status="active",
            )
            db.add(conv)
            db.commit()
            
            for i in range(3):
                log = SentimentLog(
                    employee_id=test_user.id,
                    message_id=uuid4(),
                    conversation_id=conv.id,
                    score=30,
                    label="negative",
                    emotion="frustration",
                )
                db.add(log)
        db.commit()
        
        summary = risk_scorer.get_employee_risk_summary(test_user.id, days=1)
        assert summary["conversation_count"] == 2
        assert summary["total_negative_messages"] == 6
        assert summary["requires_attention"] is True
        assert "frustration" in summary["top_concerns"]

    def test_empty_conversation_returns_none(self, db, risk_scorer):
        """Empty conversation should return None."""
        metrics = risk_scorer.score_conversation(uuid4())
        assert metrics is None
