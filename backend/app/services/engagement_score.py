"""
Engagement Score Service - Calculates real employee engagement scores.

Engagement Score Formula:
- Positive sentiment interactions: +points
- Negative sentiment interactions: -points
- Survey participation: +points
- Ticket resolution rate: +points
- Conversation frequency: +points
- Days since last interaction: -points

Score ranges from 0-100.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from ..models.conversation import Message, Conversation, SentimentLabel
from ..core.time import utcnow_naive
from ..models.ticket import Ticket, TicketStatus
from ..models.survey import Survey, SurveyResponse


class EngagementScore:
    """Calculates and tracks employee engagement scores."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_user_engagement(
        self, 
        user_id: UUID, 
        days: int = 30
    ) -> Dict:
        """Calculate engagement score for a specific user."""
        
        sentiment_score = self._calculate_sentiment_score(user_id, days)
        participation_score = self._calculate_participation_score(user_id, days)
        frequency_score = self._calculate_frequency_score(user_id, days)
        recency_score = self._calculate_recency_score(user_id)
        
        weights = {
            "sentiment": 0.30,
            "participation": 0.25,
            "frequency": 0.25,
            "recency": 0.20
        }
        
        weighted_score = (
            sentiment_score * weights["sentiment"] +
            participation_score * weights["participation"] +
            frequency_score * weights["frequency"] +
            recency_score * weights["recency"]
        )
        
        engagement_score = max(0, min(100, weighted_score))
        
        return {
            "engagement_score": round(engagement_score, 1),
            "sentiment_score": round(sentiment_score, 1),
            "participation_score": round(participation_score, 1),
            "frequency_score": round(frequency_score, 1),
            "recency_score": round(recency_score, 1),
            "score_breakdown": {
                "sentiment": weights["sentiment"],
                "participation": weights["participation"],
                "frequency": weights["frequency"],
                "recency": weights["recency"]
            }
        }
    
    def _calculate_sentiment_score(self, user_id: UUID, days: int) -> float:
        """Calculate score based on sentiment of messages."""
        cutoff = utcnow_naive() - timedelta(days=days)
        
        messages = self.db.query(Message).join(
            Conversation
        ).filter(
            and_(
                Conversation.user_id == user_id,
                Message.sentiment.isnot(None),
                Message.created_at >= cutoff
            )
        ).all()
        
        if not messages:
            return 50.0
        
        positive = sum(1 for m in messages if m.sentiment == SentimentLabel.positive)
        neutral = sum(1 for m in messages if m.sentiment == SentimentLabel.neutral)
        negative = sum(1 for m in messages if m.sentiment == SentimentLabel.negative)
        
        total = positive + neutral + negative
        if total == 0:
            return 50.0
        
        sentiment_score = ((positive * 100) + (neutral * 50) + (negative * 0)) / total
        return sentiment_score
    
    def _calculate_participation_score(self, user_id: UUID, days: int) -> float:
        """Calculate score based on survey participation."""
        cutoff = utcnow_naive() - timedelta(days=days)
        
        surveys = self.db.query(Survey).filter(
            Survey.created_at >= cutoff
        ).all()
        
        if not surveys:
            return 50.0
        
        participated = self.db.query(SurveyResponse).filter(
            SurveyResponse.user_id == user_id,
            SurveyResponse.created_at >= cutoff
        ).count()
        
        participation_rate = participated / len(surveys) if surveys else 0
        return participation_rate * 100
    
    def _calculate_frequency_score(self, user_id: UUID, days: int) -> float:
        """Calculate score based on conversation frequency."""
        cutoff = utcnow_naive() - timedelta(days=days)
        
        message_count = self.db.query(Message).join(
            Conversation
        ).filter(
            and_(
                Conversation.user_id == user_id,
                Message.created_at >= cutoff
            )
        ).count()
        
        expected_messages = days * 0.5
        
        if message_count == 0:
            return 20.0
        
        frequency_ratio = min(message_count / expected_messages, 1.5)
        return frequency_ratio * 66.67
    
    def _calculate_recency_score(self, user_id: UUID) -> float:
        """Calculate score based on how recently they interacted."""
        last_message = self.db.query(Message).join(
            Conversation
        ).filter(
            Conversation.user_id == user_id
        ).order_by(Message.created_at.desc()).first()
        
        if not last_message:
            return 30.0
        
        days_since = (utcnow_naive() - last_message.created_at).days
        
        if days_since <= 3:
            return 100.0
        elif days_since <= 7:
            return 80.0
        elif days_since <= 14:
            return 60.0
        elif days_since <= 30:
            return 40.0
        else:
            return 20.0
    
    def get_engagement_trend(
        self, 
        user_id: UUID, 
        periods: int = 3
    ) -> Dict:
        """Calculate engagement trend over time periods."""
        trends = []
        
        for i in range(periods):
            days = (i + 1) * 30
            score_data = self.calculate_user_engagement(user_id, days=days)
            trends.append({
                "period_days": days,
                "score": score_data["engagement_score"]
            })
        
        if len(trends) < 2:
            return {"trend": "insufficient_data", "change": 0}
        
        recent = trends[0]["score"]
        older = trends[-1]["score"]
        change = recent - older
        
        if change > 10:
            trend = "improving"
        elif change < -10:
            trend = "declining"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "change": round(change, 1),
            "history": trends
        }
    
    def get_all_users_engagement(self, days: int = 30) -> List[Dict]:
        """Get engagement scores for all active users."""
        from ..models.user import User
        
        users = self.db.query(User).filter(
            User.status == "active"
        ).all()
        
        results = []
        for user in users:
            score_data = self.calculate_user_engagement(user.id, days)
            results.append({
                "user_id": str(user.id),
                "user_name": user.name,
                "department": user.department.name if user.department else None,
                "engagement_score": score_data["engagement_score"]
            })
        
        results.sort(key=lambda x: x["engagement_score"], reverse=True)
        return results


def get_engagement_score(db: Session) -> EngagementScore:
    return EngagementScore(db)


__all__ = ["EngagementScore", "get_engagement_score"]
