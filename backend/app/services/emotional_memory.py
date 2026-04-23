"""
Emotional Memory Service - Tracks user mood, context, and conversation history over time.

This service provides:
- Long-term memory of user emotional states
- Conversation topic tracking
- Mood pattern detection
- Context-aware responses
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
import json

from ..models.conversation import Message, SentimentLabel
from ..models.user import User


class EmotionalMemory:
    """Tracks emotional state and context for each user over time."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_mood_history(
        self, 
        user_id: UUID, 
        days: int = 30
    ) -> List[Dict]:
        """Get sentiment history for a user over specified days."""
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        
        messages = self.db.query(Message).join(
            Message.conversation
        ).filter(
            and_(
                Message.conversation.has(user_id=user_id),
                Message.sentiment.isnot(None),
                Message.created_at >= cutoff
            )
        ).order_by(desc(Message.created_at)).all()
        
        return [
            {
                "sentiment": m.sentiment.value if m.sentiment else None,
                "intent": m.intent,
                "topic": self._extract_topic(m.message_text),
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
    
    def get_current_mood(self, user_id: UUID, lookback_messages: int = 10) -> str:
        """Get the user's current mood based on recent messages."""
        messages = self.db.query(Message).join(
            Message.conversation
        ).filter(
            and_(
                Message.conversation.has(user_id=user_id),
                Message.sentiment.isnot(None)
            )
        ).order_by(desc(Message.created_at)).limit(lookback_messages).all()
        
        if not messages:
            return "neutral"
        
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        for m in messages:
            if m.sentiment:
                sentiment_counts[m.sentiment.value] += 1
        
        return max(sentiment_counts, key=sentiment_counts.get)
    
    def get_mood_trend(self, user_id: UUID, days: int = 30) -> Dict:
        """Calculate mood trend over time (improving, declining, stable)."""
        history = self.get_user_mood_history(user_id, days)
        
        if len(history) < 3:
            return {"trend": "insufficient_data", "change_percent": 0}
        
        midpoint = len(history) // 2
        first_half = history[midpoint:]
        second_half = history[:midpoint]
        
        def calc_avg(messages):
            scores = []
            for m in messages:
                if m["sentiment"] == "positive":
                    scores.append(1)
                elif m["sentiment"] == "negative":
                    scores.append(-1)
                else:
                    scores.append(0)
            return sum(scores) / len(scores) if scores else 0
        
        first_avg = calc_avg(first_half)
        second_avg = calc_avg(second_half)
        
        change = second_avg - first_avg
        
        if change > 0.3:
            trend = "improving"
        elif change < -0.3:
            trend = "declining"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "change_percent": round(change * 100, 1),
            "message_count": len(history)
        }
    
    def get_conversation_topics(self, user_id: UUID, limit: int = 10) -> List[str]:
        """Extract recurring conversation topics for a user."""
        messages = self.db.query(Message).join(
            Message.conversation
        ).filter(
            and_(
                Message.conversation.has(user_id=user_id),
                Message.intent.isnot(None)
            )
        ).order_by(desc(Message.created_at)).limit(50).all()
        
        topics = {}
        for m in messages:
            if m.intent:
                topics[m.intent] = topics.get(m.intent, 0) + 1
        
        sorted_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_topics[:limit]]
    
    def get_user_context(self, user_id: UUID) -> Dict:
        """Get comprehensive context for a user for personalized responses."""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return {}
        
        current_mood = self.get_current_mood(user_id)
        mood_trend = self.get_mood_trend(user_id)
        topics = self.get_conversation_topics(user_id)
        
        department_name = None
        try:
            # Prefer `department_id` but safely support legacy `department` attrs.
            dept_id = getattr(user, 'department_id', None)
            if not dept_id:
                legacy_dept = getattr(user, 'department', None)
                dept_id = getattr(legacy_dept, 'id', None) if legacy_dept else None
            if dept_id:
                from ..models.department import Department
                dept = self.db.query(Department).filter(Department.id == dept_id).first()
                department_name = dept.name if dept else str(dept_id)
        except Exception:
            pass
        
        return {
            "user_name": user.name,
            "department": department_name,
            "role": user.role.value if user.role else None,
            "current_mood": current_mood,
            "mood_trend": mood_trend,
            "recent_topics": topics,
            "last_interaction": self._get_last_interaction(user_id)
        }
    
    def _get_last_interaction(self, user_id: UUID) -> Optional[str]:
        """Get ISO timestamp of last interaction."""
        message = self.db.query(Message).join(
            Message.conversation
        ).filter(
            Message.conversation.has(user_id=user_id)
        ).order_by(desc(Message.created_at)).first()
        
        if message:
            return message.created_at.isoformat()
        return None
    
    def _extract_topic(self, text: str) -> str:
        """Simple topic extraction from message text."""
        text_lower = text.lower()
        
        topic_keywords = {
            "leave": ["leave", "vacation", "time off", "pto", "sick", "absence"],
            "policy": ["policy", "rule", "guideline", "procedure"],
            "benefits": ["benefits", "insurance", "salary", "bonus", "401k"],
            "manager": ["manager", "boss", "supervisor", "lead"],
            "workload": ["workload", "deadline", "busy", "overwhelmed", "stress"],
            "team": ["team", "colleague", "coworker", "collab"],
            "promotion": ["promotion", "career", "growth", "raise"]
        }
        
        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return topic
        
        return "general"
    
    def check_wellbeing_concerns(self, user_id: UUID) -> Optional[Dict]:
        """Check if there are any wellbeing concerns based on conversation patterns."""
        recent = self.get_user_mood_history(user_id, days=7)
        
        if len(recent) < 3:
            return None
        
        negative_count = sum(1 for m in recent if m["sentiment"] == "negative")
        negative_ratio = negative_count / len(recent)
        
        workload_mentions = sum(
            1 for m in recent 
            if m.get("topic") == "workload" and m["sentiment"] == "negative"
        )
        
        concerns = []
        if negative_ratio > 0.4:
            concerns.append("frequent_negative_sentiment")
        if workload_mentions >= 2:
            concerns.append("workload_stress")
        
        if not concerns:
            return None
        
        return {
            "concerns": concerns,
            "negative_ratio": round(negative_ratio, 2),
            "message_count": len(recent)
        }


def get_emotional_memory(db: Session) -> EmotionalMemory:
    return EmotionalMemory(db)


__all__ = ["EmotionalMemory", "get_emotional_memory"]
