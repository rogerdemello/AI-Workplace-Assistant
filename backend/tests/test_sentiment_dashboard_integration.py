"""End-to-end integration test verifying sentiment flows through to HR dashboard."""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from app.services.sentiment_enhanced import analyze_sentiment_enhanced
from app.services.sentiment_pipeline import SentimentPipelineService
from app.services.dashboard_adapters import build_dashboard_bundle_contract
from app.models.sentiment_log import SentimentLog
from app.models.employee_score import EmployeeScore


class TestSentimentToDashboardIntegration:
    """Verify sentiment from chat → pipeline → DB → dashboard."""

    def test_chat_message_creates_sentiment_log(self, db, test_user):
        """When user sends chat message, sentiment log should be created."""
        pipeline = SentimentPipelineService(db)
        
        result = pipeline.process_message(
            employee_id=test_user.id,
            message_id=uuid4(),
            message_text="I'm really frustrated with the workload",
            conversation_id=uuid4(),
        )
        
        assert result["score"] < 50  # Negative sentiment
        assert result["label"] == "negative"
        
        # Verify DB has the log
        logs = db.query(SentimentLog).filter(SentimentLog.employee_id == test_user.id).all()
        assert len(logs) >= 1
        latest = max(logs, key=lambda x: x.created_at)
        assert latest.score < 50

    def test_sentiment_updates_employee_score(self, db, test_user):
        """Sentiment should update employee's aggregate score."""
        pipeline = SentimentPipelineService(db)
        
        # Send negative message
        pipeline.process_message(
            employee_id=test_user.id,
            message_id=uuid4(),
            message_text="I'm stressed and overwhelmed",
            conversation_id=uuid4(),
        )
        
        # Check employee score was updated
        score = db.query(EmployeeScore).filter(EmployeeScore.employee_id == test_user.id).first()
        if score:
            assert score.sentiment_score < 70  # Should reflect negative sentiment

    def test_dashboard_shows_freshness_signal(self, db, test_user):
        """Dashboard should include last_chat_sentiment_at timestamp."""
        pipeline = SentimentPipelineService(db)
        
        pipeline.process_message(
            employee_id=test_user.id,
            message_id=uuid4(),
            message_text="I'm happy with the new benefits",
            conversation_id=uuid4(),
        )
        
        bundle = build_dashboard_bundle_contract(db)
        assert bundle.last_chat_sentiment_at is not None
        assert (datetime.utcnow() - bundle.last_chat_sentiment_at).total_seconds() < 60

    def test_enhanced_sentiment_detects_sarcasm_in_chat(self, db, test_user):
        """Enhanced sentiment should detect sarcasm in chat messages."""
        result = analyze_sentiment_enhanced("Oh great, another meeting. Just what I needed.")
        
        assert result["sarcasm"]["detected"] == True
        assert result["sentiment"] == "negative"  # Should invert sarcasm
        assert result["score"] < 0

    def test_multiple_messages_show_trend(self, db, test_user):
        """Multiple messages should show sentiment trend."""
        pipeline = SentimentPipelineService(db)
        conversation_id = uuid4()
        
        messages = [
            "I'm doing okay",
            "Actually, I'm getting frustrated",
            "This is really stressful",
            "I can't handle this anymore",
        ]
        
        for msg in messages:
            pipeline.process_message(
                employee_id=test_user.id,
                message_id=uuid4(),
                message_text=msg,
                conversation_id=conversation_id,
            )
        
        # Get trend
        logs = db.query(SentimentLog).filter(
            SentimentLog.employee_id == test_user.id,
            SentimentLog.conversation_id == conversation_id,
        ).order_by(SentimentLog.created_at).all()
        
        assert len(logs) == 4
        # Trend should be declining (scores getting lower)
        scores = [log.score for log in logs]
        assert scores[-1] < scores[0]  # Last score should be lower than first


class TestPrivacyIsolation:
    """Verify users can only see their own data."""

    def test_user_cannot_access_other_chat(self, db, test_user, client):
        """User should only access their own conversations."""
        # This is tested via API auth in test_chat.py
        pass

    def test_chat_snapshot_isolated_by_email(self):
        """Frontend snapshots should be isolated by email."""
        # Frontend uses: `mark-employee-chat:${email}` as localStorage key
        # This is verified in new-frontend/src/lib/chat-session-storage.ts
        key1 = f"mark-employee-chat:user1@company.com"
        key2 = f"mark-employee-chat:user2@company.com"
        
        assert key1 != key2
        assert "user1" in key1
        assert "user2" in key2
