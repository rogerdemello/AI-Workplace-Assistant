"""Conversation-level risk scoring system.

Aggregates sentiment across entire conversations to identify at-risk employees
and flag conversations that need HR attention.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.sentiment_log import SentimentLog
from ..models.conversation import Conversation

logger = logging.getLogger(__name__)


@dataclass
class ConversationRiskMetrics:
    """Risk metrics for a single conversation."""
    conversation_id: UUID
    employee_id: UUID
    total_messages: int
    negative_count: int
    neutral_count: int
    positive_count: int
    average_sentiment: float
    sentiment_trend: str  # improving, declining, stable
    risk_score: int  # 0-100
    dominant_emotion: Optional[str]
    emotions_detected: List[str]
    alert_level: str  # none, low, medium, high, critical
    requires_hr_attention: bool


class ConversationRiskScorer:
    """Calculate risk scores for conversations based on sentiment history."""

    # Risk thresholds
    RISK_LOW = 30
    RISK_MEDIUM = 50
    RISK_HIGH = 70
    RISK_CRITICAL = 85

    def __init__(self, db: Session):
        self.db = db

    def score_conversation(self, conversation_id: UUID) -> Optional[ConversationRiskMetrics]:
        """Calculate risk metrics for a conversation."""
        logs = (
            self.db.query(SentimentLog)
            .filter(SentimentLog.conversation_id == conversation_id)
            .order_by(SentimentLog.created_at)
            .all()
        )

        if not logs:
            return None

        employee_id = logs[0].employee_id
        total = len(logs)
        
        # Count sentiments
        negative_count = sum(1 for log in logs if log.label == "negative")
        neutral_count = sum(1 for log in logs if log.label == "neutral")
        positive_count = sum(1 for log in logs if log.label == "positive")
        
        # Calculate average
        scores = [log.score for log in logs]
        average = sum(scores) / len(scores) if scores else 50
        
        # Calculate trend
        trend = self._calculate_trend(scores)
        
        # Calculate risk score
        risk = self._calculate_risk_score(
            logs=logs,
            negative_count=negative_count,
            total=total,
            trend=trend,
        )
        
        # Detect emotions
        emotions = [log.emotion for log in logs if log.emotion and log.emotion != "neutral"]
        dominant = self._get_dominant_emotion(emotions)
        unique_emotions = list(set(emotions))
        
        # Determine alert level
        alert_level = self._get_alert_level(risk)
        requires_hr = risk >= self.RISK_HIGH
        
        return ConversationRiskMetrics(
            conversation_id=conversation_id,
            employee_id=employee_id,
            total_messages=total,
            negative_count=negative_count,
            neutral_count=neutral_count,
            positive_count=positive_count,
            average_sentiment=round(average, 1),
            sentiment_trend=trend,
            risk_score=risk,
            dominant_emotion=dominant,
            emotions_detected=unique_emotions,
            alert_level=alert_level,
            requires_hr_attention=requires_hr,
        )

    def score_employee_conversations(
        self,
        employee_id: UUID,
        days: int = 7,
    ) -> List[ConversationRiskMetrics]:
        """Get risk metrics for all employee conversations in time window."""
        since = datetime.utcnow() - timedelta(days=days)
        
        conversations = (
            self.db.query(Conversation)
            .filter(
                Conversation.user_id == employee_id,
                Conversation.started_at >= since,
            )
            .all()
        )
        
        results = []
        for conv in conversations:
            metrics = self.score_conversation(conv.id)
            if metrics:
                results.append(metrics)
        
        # Sort by risk score descending
        results.sort(key=lambda x: x.risk_score, reverse=True)
        return results

    def get_high_risk_conversations(
        self,
        min_risk: int = 70,
        limit: int = 50,
    ) -> List[ConversationRiskMetrics]:
        """Get all high-risk conversations across all employees."""
        # Get recent conversations with sentiment logs
        recent_convs = (
            self.db.query(Conversation)
            .join(SentimentLog, Conversation.id == SentimentLog.conversation_id)
            .filter(
                Conversation.started_at >= datetime.utcnow() - timedelta(days=7),
            )
            .group_by(Conversation.id)
            .having(func.count(SentimentLog.id) >= 2)  # At least 2 messages
            .limit(limit * 2)  # Get more than needed for filtering
            .all()
        )
        
        results = []
        for conv in recent_convs:
            metrics = self.score_conversation(conv.id)
            if metrics and metrics.risk_score >= min_risk:
                results.append(metrics)
        
        # Sort by risk score descending
        results.sort(key=lambda x: x.risk_score, reverse=True)
        return results[:limit]

    def get_employee_risk_summary(self, employee_id: UUID, days: int = 7) -> Dict:
        """Get aggregated risk summary for an employee."""
        conversations = self.score_employee_conversations(employee_id, days)
        
        if not conversations:
            return {
                "employee_id": str(employee_id),
                "conversation_count": 0,
                "average_risk": 0,
                "highest_risk": 0,
                "total_negative_messages": 0,
                "requires_attention": False,
                "top_concerns": [],
            }
        
        total_negative = sum(c.negative_count for c in conversations)
        avg_risk = sum(c.risk_score for c in conversations) / len(conversations)
        highest_risk = max(c.risk_score for c in conversations)
        requires_attention = any(c.requires_hr_attention for c in conversations)
        
        # Collect top concerns (unique emotions from high-risk conversations)
        concerns = set()
        for c in conversations:
            if c.risk_score >= self.RISK_MEDIUM:
                concerns.update(c.emotions_detected)
        
        return {
            "employee_id": str(employee_id),
            "conversation_count": len(conversations),
            "average_risk": round(avg_risk, 1),
            "highest_risk": highest_risk,
            "total_negative_messages": total_negative,
            "requires_attention": requires_attention,
            "top_concerns": sorted(list(concerns)),
        }

    def _calculate_trend(self, scores: List[int]) -> str:
        """Calculate sentiment trend from score list."""
        if len(scores) < 3:
            return "stable"
        
        # Compare first half vs second half
        mid = len(scores) // 2
        first_avg = sum(scores[:mid]) / max(mid, 1)
        second_avg = sum(scores[mid:]) / max(len(scores) - mid, 1)
        
        diff = second_avg - first_avg
        
        if diff > 10:
            return "improving"
        elif diff < -10:
            return "declining"
        return "stable"

    def _calculate_risk_score(
        self,
        *,
        logs: List[SentimentLog],
        negative_count: int,
        total: int,
        trend: str,
    ) -> int:
        """Calculate composite risk score (0-100)."""
        if total == 0:
            return 0
        
        risk = 0
        
        # Factor 1: Negative ratio (0-40 points)
        negative_ratio = negative_count / total
        risk += int(negative_ratio * 40)
        
        # Factor 2: Trend (0-25 points)
        if trend == "declining":
            risk += 25
        elif trend == "stable" and negative_ratio > 0.3:
            risk += 10
        
        # Factor 3: Severity of emotions (0-25 points)
        critical_emotions = {"burnout", "exhaustion", "betrayal", "injustice", "panic"}
        high_emotions = {"anxiety", "frustration", "anger", "overwhelm"}
        medium_emotions = {"sadness", "loneliness", "disappointment", "confusion"}
        
        for log in logs:
            if log.emotion in critical_emotions:
                risk += 8
            elif log.emotion in high_emotions:
                risk += 5
            elif log.emotion in medium_emotions:
                risk += 3
        
        # Factor 4: Very low sentiment scores (0-10 points)
        very_low = sum(1 for log in logs if log.score < 20)
        risk += min(10, very_low * 5)
        
        # Factor 5: High negative ratio bonus (0-10 points)
        if negative_ratio >= 0.8:
            risk += 10
        
        return min(100, risk)

    def _get_dominant_emotion(self, emotions: List[str]) -> Optional[str]:
        """Get the most frequent emotion from a list."""
        if not emotions:
            return None
        
        emotion_counts = {}
        for emotion in emotions:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        return max(emotion_counts, key=emotion_counts.get)

    def _get_alert_level(self, risk: int) -> str:
        """Map risk score to alert level."""
        if risk >= self.RISK_CRITICAL:
            return "critical"
        elif risk >= self.RISK_HIGH:
            return "high"
        elif risk >= self.RISK_MEDIUM:
            return "medium"
        elif risk >= self.RISK_LOW:
            return "low"
        return "none"


def get_conversation_risk_scorer(db: Session) -> ConversationRiskScorer:
    """Factory function for ConversationRiskScorer."""
    return ConversationRiskScorer(db)
