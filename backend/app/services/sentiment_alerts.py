"""Real-time sentiment alerting system for HR notifications.

Triggers alerts when:
- Single message sentiment drops below threshold
- Specific emotions detected (burnout, anxiety, etc.)
- Sustained negative patterns across multiple messages
- Conversation-level risk score exceeds threshold
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..core.time import utcnow_naive
from ..models.employee_score import EmployeeScore
from ..models.hr_notification import HrNotification
from ..models.sentiment_log import SentimentLog
from ..models.conversation import Conversation

logger = logging.getLogger(__name__)

# Alert configuration
DEFAULT_SENTIMENT_THRESHOLD = 30  # Score below this triggers alert
DEFAULT_RISK_THRESHOLD = 70  # Risk score above this triggers alert
DEFAULT_EMOTION_ALERTS: Set[str] = {"burnout", "exhaustion", "betrayal", "injustice", "panic"}
DEFAULT_COOLDOWN_MINUTES = 30  # Minimum time between alerts for same employee

# Emotion severity mapping
EMOTION_SEVERITY = {
    "burnout": "critical",
    "exhaustion": "high",
    "betrayal": "high",
    "injustice": "high",
    "panic": "critical",
    "anxiety": "medium",
    "frustration": "medium",
    "anger": "medium",
    "sadness": "medium",
    "loneliness": "medium",
    "overwhelm": "high",
}


def _parse_emotion_triggers(raw: object) -> Set[str]:
    """Parse the comma-separated EMOTION_ALERT_TRIGGERS setting into a set.

    Falls back to the defaults when the value is blank or unparseable, so a
    typo in configuration can't silently switch emotion alerting off.
    """
    if isinstance(raw, (set, frozenset, list, tuple)):
        values = {str(item).strip().lower() for item in raw if str(item).strip()}
        return values or set(DEFAULT_EMOTION_ALERTS)
    if isinstance(raw, str):
        values = {part.strip().lower() for part in raw.split(",") if part.strip()}
        return values or set(DEFAULT_EMOTION_ALERTS)
    return set(DEFAULT_EMOTION_ALERTS)


class SentimentAlertService:
    """Service for creating HR alerts based on sentiment analysis."""

    def __init__(self, db: Session):
        self.db = db
        # Read settings directly: these are declared on Settings, so a getattr
        # fallback would silently mask a rename and pin the old default forever.
        self.sentiment_threshold = int(settings.SENTIMENT_ALERT_THRESHOLD)
        self.risk_threshold = int(settings.RISK_ALERT_THRESHOLD)
        self.emotion_alerts = _parse_emotion_triggers(settings.EMOTION_ALERT_TRIGGERS)
        self.cooldown_minutes = int(settings.ALERT_COOLDOWN_MINUTES)

    def process_message_sentiment(
        self,
        *,
        employee_id: UUID,
        message_id: UUID,
        sentiment_score: int,
        sentiment_label: str,
        emotion: Optional[str] = None,
        conversation_id: Optional[UUID] = None,
    ) -> List[str]:
        """
        Process a single message's sentiment and create alerts if needed.
        
        Returns list of alert IDs created.
        """
        alerts_created: List[str] = []

        # Check 1: Single message sentiment threshold
        if sentiment_score <= self.sentiment_threshold:
            alert_id = self._create_sentiment_alert(
                employee_id=employee_id,
                alert_type="sentiment_threshold",
                title="Low sentiment detected",
                body=f"Employee sentiment score dropped to {sentiment_score}/100",
                severity="high",
                metadata={
                    "sentiment_score": sentiment_score,
                    "sentiment_label": sentiment_label,
                    "message_id": str(message_id),
                },
            )
            if alert_id:
                alerts_created.append(alert_id)

        # Check 2: Emotion-based alerts
        if emotion and emotion.lower() in self.emotion_alerts:
            severity = EMOTION_SEVERITY.get(emotion.lower(), "medium")
            alert_id = self._create_sentiment_alert(
                employee_id=employee_id,
                alert_type="emotion_detected",
                title=f"{emotion.title()} detected",
                body=f"Employee expressed {emotion} in conversation",
                severity=severity,
                metadata={
                    "emotion": emotion,
                    "message_id": str(message_id),
                },
            )
            if alert_id:
                alerts_created.append(alert_id)

        # Check 3: Sustained negative pattern
        if sentiment_label == "negative":
            negative_count = self._count_recent_negative_sentiments(employee_id)
            if negative_count >= 3:  # 3+ negative messages in window
                alert_id = self._create_sentiment_alert(
                    employee_id=employee_id,
                    alert_type="sustained_negative",
                    title="Sustained negative sentiment",
                    body=f"Employee has shown {negative_count} negative sentiments recently",
                    severity="high",
                    metadata={
                        "negative_count": negative_count,
                    },
                )
                if alert_id:
                    alerts_created.append(alert_id)

        # Check 4: Conversation risk score
        if conversation_id:
            conversation_risk = self._calculate_conversation_risk(conversation_id)
            if conversation_risk >= self.risk_threshold:
                alert_id = self._create_sentiment_alert(
                    employee_id=employee_id,
                    alert_type="conversation_risk",
                    title="High conversation risk",
                    body=f"Conversation risk score reached {conversation_risk}/100",
                    severity="critical",
                    metadata={
                        "conversation_risk": conversation_risk,
                        "conversation_id": str(conversation_id),
                    },
                )
                if alert_id:
                    alerts_created.append(alert_id)

        return alerts_created

    def _create_sentiment_alert(
        self,
        *,
        employee_id: UUID,
        alert_type: str,
        title: str,
        body: str,
        severity: str,
        metadata: Optional[Dict] = None,
    ) -> Optional[str]:
        """Create an HR notification with cooldown check."""
        # Check cooldown
        cooldown = timedelta(minutes=self.cooldown_minutes)
        since = utcnow_naive() - cooldown
        
        existing = (
            self.db.query(HrNotification.id)
            .filter(
                HrNotification.actor_id == employee_id,
                HrNotification.notification_type == f"sentiment_alert:{alert_type}",
                HrNotification.created_at >= since,
            )
            .first()
        )
        
        if existing:
            return None

        # Create notification
        notification = HrNotification(
            ticket_id=None,
            actor_id=employee_id,
            title=title,
            body=body,
            notification_type=f"sentiment_alert:{alert_type}",
            severity=severity,
        )
        self.db.add(notification)
        self.db.commit()
        
        logger.info(
            "Sentiment alert created: %s for employee %s (severity: %s)",
            alert_type,
            employee_id,
            severity,
        )
        
        return str(notification.id)

    def _count_recent_negative_sentiments(self, employee_id: UUID, hours: int = 24) -> int:
        """Count negative sentiment logs in recent hours."""
        since = utcnow_naive() - timedelta(hours=hours)
        count = (
            self.db.query(func.count(SentimentLog.id))
            .filter(
                SentimentLog.employee_id == employee_id,
                SentimentLog.label == "negative",
                SentimentLog.created_at >= since,
            )
            .scalar()
        )
        return count or 0

    def _calculate_conversation_risk(self, conversation_id: UUID) -> int:
        """Calculate risk score for a conversation based on sentiment logs."""
        logs = (
            self.db.query(SentimentLog)
            .filter(SentimentLog.conversation_id == conversation_id)
            .order_by(SentimentLog.created_at)
            .all()
        )
        
        if not logs:
            return 0

        # Calculate weighted risk
        negative_count = sum(1 for log in logs if log.label == "negative")
        neutral_count = sum(1 for log in logs if log.label == "neutral")
        total = len(logs)
        
        # Risk factors
        negative_ratio = negative_count / total
        
        # Check for declining trend
        scores = [log.score for log in logs]
        trend_risk = 0
        if len(scores) >= 3:
            # If scores are declining
            if scores[-1] < scores[0] - 15:
                trend_risk = 20
        
        # Emotion risk
        emotion_risk = 0
        for log in logs:
            if log.emotion in EMOTION_SEVERITY:
                if EMOTION_SEVERITY[log.emotion] == "critical":
                    emotion_risk = max(emotion_risk, 30)
                elif EMOTION_SEVERITY[log.emotion] == "high":
                    emotion_risk = max(emotion_risk, 20)
                elif EMOTION_SEVERITY[log.emotion] == "medium":
                    emotion_risk = max(emotion_risk, 10)
        
        # High negative ratio bonus
        ratio_bonus = 10 if negative_ratio >= 0.8 else 0
        
        # Calculate final risk score (0-100)
        risk = int((negative_ratio * 50) + trend_risk + emotion_risk + ratio_bonus)
        return min(100, risk)

    def get_active_alerts(self, hours: int = 24) -> List[Dict]:
        """Get all active sentiment alerts within time window."""
        since = utcnow_naive() - timedelta(hours=hours)
        notifications = (
            self.db.query(HrNotification)
            .filter(
                HrNotification.notification_type.like("sentiment_alert:%"),
                HrNotification.created_at >= since,
            )
            .order_by(HrNotification.created_at.desc())
            .all()
        )
        
        return [
            {
                "id": str(n.id),
                "employee_id": str(n.actor_id),
                "type": n.notification_type.replace("sentiment_alert:", ""),
                "title": n.title,
                "body": n.body,
                "severity": n.severity,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ]

    def dismiss_alert(self, alert_id) -> bool:
        """Dismiss an alert by ID. Accepts string or UUID."""
        from uuid import UUID as UUIDType
        if isinstance(alert_id, str):
            alert_id = UUIDType(alert_id)
        
        notification = (
            self.db.query(HrNotification)
            .filter(HrNotification.id == alert_id)
            .first()
        )
        if notification:
            # Soft delete - mark as read
            notification.severity = "dismissed"
            self.db.commit()
            return True
        return False


def get_sentiment_alert_service(db: Session) -> SentimentAlertService:
    """Factory function for SentimentAlertService."""
    return SentimentAlertService(db)
