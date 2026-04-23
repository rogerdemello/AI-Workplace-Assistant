"""
Proactive Wellbeing Monitor - Detects at-risk employees and triggers HR alerts.

This service:
- Monitors sentiment trends over time
- Detects warning patterns (declining mood, burnout signs)
- Triggers alerts for HR when employees need attention
- Supports anonymous escalation
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import json
import logging

from ..events import event_bus
from ..events.events import DomainEvent, EVENT_RISK_DETECTED
from ..models.conversation import Message, Conversation
from ..core.time import utcnow_naive
from ..models.user import User, UserStatus
from .emotional_memory import EmotionalMemory
from .sentiment import SentimentService

logger = logging.getLogger(__name__)


class WellbeingAlert:
    """Represents an alert about an employee's wellbeing."""
    
    def __init__(
        self,
        user_id: UUID,
        alert_type: str,
        severity: str,
        message: str,
        details: Dict,
        is_anonymous: bool = True
    ):
        self.user_id = user_id
        self.alert_type = alert_type
        self.severity = severity
        self.message = message
        self.details = details
        self.is_anonymous = is_anonymous
        self.created_at = utcnow_naive()
    
    def to_dict(self) -> Dict:
        result = {
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "is_anonymous": self.is_anonymous,
            "created_at": self.created_at.isoformat()
        }
        if not self.is_anonymous:
            result["user_id"] = str(self.user_id)
        return result


class ProactiveWellbeingMonitor:
    """
    Monitors employee wellbeing and triggers alerts for HR.
    
    Alert Types:
    - declining_mood: Sentiment has dropped significantly over time
    - burnout_risk: Multiple negative interactions about workload
    - isolation_signs: Decreased engagement/conversation frequency
    - crisis_signs: Expressing serious distress
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.emotional_memory = EmotionalMemory(db)
        self.sentiment_service = SentimentService()
        self._alert_history: List[Dict] = []
    
    def check_user_wellbeing(
        self, 
        user_id: UUID,
        force_check: bool = False
    ) -> Optional[WellbeingAlert]:
        """Check a specific user's wellbeing and return alert if needed."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        alerts = []
        
        mood_trend = self.emotional_memory.get_mood_trend(user_id, days=30)
        if mood_trend.get("trend") == "declining":
            alerts.append(self._create_declining_mood_alert(
                user_id, mood_trend
            ))
        
        burnout_risk = self._check_burnout_risk(user_id)
        if burnout_risk:
            alerts.append(burnout_risk)
        
        isolation_risk = self._check_isolation_signs(user_id)
        if isolation_risk:
            alerts.append(isolation_risk)
        
        crisis_signs = self._check_crisis_signs(user_id)
        if crisis_signs:
            alerts.append(crisis_signs)
        
        if not alerts and not force_check:
            return None
        
        highest_severity_alert = max(
            alerts, 
            key=lambda a: {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(a.severity, 0)
        ) if alerts else None
        
        if highest_severity_alert:
            self._alert_history.append(highest_severity_alert.to_dict())
            try:
                event_bus.publish(
                    DomainEvent(
                        name=EVENT_RISK_DETECTED,
                        payload={
                            "user_id": str(user_id),
                            "alert_type": highest_severity_alert.alert_type,
                            "severity": highest_severity_alert.severity,
                            "is_anonymous": highest_severity_alert.is_anonymous,
                        },
                    )
                )
            except Exception:
                logger.warning("Failed to publish risk_detected event", exc_info=True)
        
        return highest_severity_alert
    
    def check_all_users(self) -> List[WellbeingAlert]:
        """Check wellbeing for all active users. Returns list of alerts."""
        users = self.db.query(User).filter(User.status == UserStatus.active).all()
        
        alerts = []
        for user in users:
            alert = self.check_user_wellbeing(user.id)
            if alert:
                alerts.append(alert)
        
        return alerts
    
    def get_alert_history(
        self, 
        user_id: Optional[UUID] = None,
        alert_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get historical alerts, optionally filtered."""
        results = self._alert_history[-limit:]
        
        if user_id:
            results = [a for a in results if a.get("user_id") == str(user_id)]
        if alert_type:
            results = [a for a in results if a.get("alert_type") == alert_type]
        
        return results
    
    def _create_declining_mood_alert(
        self, 
        user_id: UUID,
        mood_trend: Dict
    ) -> WellbeingAlert:
        return WellbeingAlert(
            user_id=user_id,
            alert_type="declining_mood",
            severity="medium",
            message="Employee's mood has been declining over the past weeks",
            details={
                "trend": mood_trend.get("trend"),
                "change_percent": mood_trend.get("change_percent"),
                "message_count": mood_trend.get("message_count")
            }
        )
    
    def _check_burnout_risk(self, user_id: UUID) -> Optional[WellbeingAlert]:
        """Check for burnout risk indicators."""
        recent = self.emotional_memory.get_user_mood_history(user_id, days=14)
        
        workload_negative = sum(
            1 for m in recent 
            if m.get("topic") == "workload" and m.get("sentiment") == "negative"
        )
        
        if workload_negative >= 3:
            return WellbeingAlert(
                user_id=user_id,
                alert_type="burnout_risk",
                severity="high",
                message="Employee showing signs of work-related stress",
                details={
                    "workload_complaints": workload_negative,
                    "total_messages": len(recent),
                    "recommendation": "Consider manager check-in or workload review"
                }
            )
        
        return None
    
    def _check_isolation_signs(self, user_id: UUID) -> Optional[WellbeingAlert]:
        """Check for signs of decreased engagement."""
        recent_messages = self.db.query(Message).join(
            Conversation
        ).filter(
            and_(
                Conversation.user_id == user_id,
                Message.created_at >= utcnow_naive() - timedelta(days=30)
            )
        ).count()
        
        older_messages = self.db.query(Message).join(
            Conversation
        ).filter(
            and_(
                Conversation.user_id == user_id,
                Message.created_at >= utcnow_naive() - timedelta(days=60),
                Message.created_at < utcnow_naive() - timedelta(days=30)
            )
        ).count()
        
        if older_messages > 5 and recent_messages <= 2:
            return WellbeingAlert(
                user_id=user_id,
                alert_type="isolation_signs",
                severity="low",
                message="Employee engagement has decreased significantly",
                details={
                    "recent_messages": recent_messages,
                    "previous_messages": older_messages,
                    "recommendation": "Reach out to check in"
                }
            )
        
        return None
    
    def _check_crisis_signs(self, user_id: UUID) -> Optional[WellbeingAlert]:
        """Check for crisis-level indicators that need immediate attention."""
        crisis_keywords = [
            "want to hurt", "want to die", "suicide", "self harm",
            "can't go on", "better off without me"
        ]
        
        recent_messages = self.db.query(Message).join(
            Conversation
        ).filter(
            and_(
                Conversation.user_id == user_id,
                Message.created_at >= utcnow_naive() - timedelta(days=7)
            )
        ).all()
        
        for msg in recent_messages:
            text_lower = msg.message_text.lower()
            if any(kw in text_lower for kw in crisis_keywords):
                return WellbeingAlert(
                    user_id=user_id,
                    alert_type="crisis_signs",
                    severity="critical",
                    message="Employee expressing crisis-level distress - immediate intervention required",
                    details={
                        "message_preview": msg.message_text[:100],
                        "recommendation": "IMMEDIATE: Connect with EAP or crisis hotline"
                    },
                    is_anonymous=False
                )
        
        return None
    
    def should_proactive_outreach(
        self, 
        user_id: UUID
    ) -> Dict:
        """Determine if proactive outreach is needed."""
        alert = self.check_user_wellbeing(user_id)
        
        if not alert:
            return {
                "needs_outreach": False,
                "reason": "No wellbeing concerns detected"
            }
        
        return {
            "needs_outreach": True,
            "reason": alert.message,
            "severity": alert.severity,
            "recommendation": alert.details.get("recommendation", "Check in with employee")
        }


def get_proactive_monitor(db: Session) -> ProactiveWellbeingMonitor:
    return ProactiveWellbeingMonitor(db)


__all__ = [
    "ProactiveWellbeingMonitor", 
    "WellbeingAlert",
    "get_proactive_monitor"
]
