from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import logging

from ..models.conversation import Conversation, Message, MessageSender, SentimentLabel
from ..core.time import utcnow_naive

logger = logging.getLogger(__name__)


class SentimentService:
    """
    Sentiment analysis service for HR assistant.
    
    Supports:
    - Text sentiment analysis (positive, neutral, negative)
    - Batch analysis
    - Trend analysis over time
    - Alert triggering for negative patterns
    
    In production, this would integrate with Azure AI Text Analytics.
    """
    
    # Word lists for simple sentiment analysis
    # In production, use Azure AI Text Analytics or similar ML model
    POSITIVE_WORDS = [
        'good', 'great', 'excellent', 'love', 'amazing', 'happy', 
        'thanks', 'thank', 'awesome', 'fantastic', 'wonderful', 
        'helpful', 'appreciate', 'pleasant', 'satisfied', 'helpful',
        'best', 'perfect', 'glad', 'pleased', 'excited'
    ]
    
    NEGATIVE_WORDS = [
        'bad', 'terrible', 'hate', 'awful', 'poor', 'worst', 
        'angry', 'frustrated', 'disappointed', 'upset', 'annoyed',
        'horrible', 'useless', 'waste', 'problem', 'issue',
        'difficult', 'confusing', 'slow', 'rude', 'unhappy'
    ]
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
    
    def analyze(self, text: str) -> Dict:
        """
        Analyze sentiment of a single text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dict with sentiment label, score (-1 to 1), and original text
        """
        if not text or not text.strip():
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "text": text
            }
        
        text_lower = text.lower()
        
        # Count positive and negative word matches
        pos_count = sum(1 for word in self.POSITIVE_WORDS if word in text_lower)
        neg_count = sum(1 for word in self.NEGATIVE_WORDS if word in text_lower)
        
        # Calculate sentiment
        if pos_count > neg_count:
            label = "positive"
            # Score ranges from 0.5 to 1.0 based on word count difference
            score = min(0.5 + (pos_count - neg_count) * 0.1, 1.0)
        elif neg_count > pos_count:
            label = "negative"
            # Score ranges from -0.5 to -1.0 based on word count difference
            score = max(-0.5 - (neg_count - pos_count) * 0.1, -1.0)
        else:
            label = "neutral"
            score = 0.0
        
        result = {
            "sentiment": label,
            "score": round(score, 3),
            "text": text
        }
        
        logger.info(f"Sentiment analysis: {label} ({score:.3f})")
        
        return result
    
    def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """
        Analyze sentiment for multiple texts.
        
        Args:
            texts: List of text strings to analyze
            
        Returns:
            List of sentiment analysis results
        """
        return [self.analyze(text) for text in texts]
    
    def get_trend(self, user_id: Optional[UUID] = None, days: int = 7) -> Dict:
        """
        Get sentiment trend analysis.
        
        In production, this would query the sentiment history from the database
        and calculate actual trends based on stored data.
        
        Args:
            user_id: Optional user ID to filter trends
            days: Number of days to analyze (default: 7)
            
        Returns:
            Dict with trend statistics
        """
        days = max(1, min(days, 90))
        end_date = utcnow_naive()
        start_date = end_date - timedelta(days=days)

        if not self.db:
            return {
                "average_sentiment": 0.0,
                "trend": "stable",
                "positive_percentage": 0.0,
                "negative_percentage": 0.0,
                "neutral_percentage": 100.0,
                "total_analyses": 0,
                "period_days": days,
            }

        query = (
            self.db.query(Message.sentiment, func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Message.sender == MessageSender.user,
                Message.created_at >= start_date,
                Message.sentiment.isnot(None),
            )
        )

        if user_id:
            query = query.filter(Conversation.user_id == user_id)

        rows = query.group_by(Message.sentiment).all()

        counts = {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
        }
        for sentiment, count in rows:
            if sentiment == SentimentLabel.positive:
                counts["positive"] += int(count)
            elif sentiment == SentimentLabel.negative:
                counts["negative"] += int(count)
            else:
                counts["neutral"] += int(count)

        total = counts["positive"] + counts["neutral"] + counts["negative"]
        if total == 0:
            return {
                "average_sentiment": 0.0,
                "trend": "stable",
                "positive_percentage": 0.0,
                "negative_percentage": 0.0,
                "neutral_percentage": 100.0,
                "total_analyses": 0,
                "period_days": days,
            }

        positive_pct = (counts["positive"] / total) * 100.0
        negative_pct = (counts["negative"] / total) * 100.0
        neutral_pct = (counts["neutral"] / total) * 100.0

        sentiment_score = (
            (counts["positive"] * 1.0)
            + (counts["neutral"] * 0.0)
            + (counts["negative"] * -1.0)
        ) / total

        if sentiment_score > 0.2:
            trend_label = "improving"
        elif sentiment_score < -0.2:
            trend_label = "declining"
        else:
            trend_label = "stable"

        return {
            "average_sentiment": round(sentiment_score, 3),
            "trend": trend_label,
            "positive_percentage": round(positive_pct, 1),
            "negative_percentage": round(negative_pct, 1),
            "neutral_percentage": round(neutral_pct, 1),
            "total_analyses": total,
            "period_days": days,
        }
    
    def should_trigger_alert(self, sentiment: str, score: float) -> bool:
        """
        Determine if negative sentiment should trigger an alert.
        
        Args:
            sentiment: Sentiment label (positive, neutral, negative)
            score: Sentiment score (-1 to 1)
            
        Returns:
            True if alert should be triggered
        """
        # Trigger alert for strongly negative sentiment
        if sentiment == "negative" and score < -0.5:
            return True
        return False
    
    def check_negative_patterns(self, recent_sentiments: List[Dict]) -> Optional[Dict]:
        """
        Check for patterns of negative sentiment that may need attention.
        
        Args:
            recent_sentiments: List of recent sentiment analysis results
            
        Returns:
            Dict with alert info if pattern detected, None otherwise
        """
        if len(recent_sentiments) < 3:
            return None
        
        negative_count = sum(1 for s in recent_sentiments if s.get("sentiment") == "negative")
        negative_ratio = negative_count / len(recent_sentiments)
        
        # Alert if more than 50% are negative in recent analyses
        if negative_ratio > 0.5:
            return {
                "alert": True,
                "message": "Pattern of negative sentiment detected",
                "negative_count": negative_count,
                "total_count": len(recent_sentiments),
                "negative_percentage": round(negative_ratio * 100, 1)
            }
        
        return None

    def log_sentiment(
        self,
        user_id: UUID,
        text: str,
        sentiment: Optional[str] = None,
    ) -> None:
        """
        Persist a sentiment observation for analytics dashboards.

        Strategy: try to write to a `sentiment_logs` table if the model
        exists, otherwise silently no-op so we never break the chat flow.
        sentiment can be 'positive', 'neutral', or 'negative'.
        """
        if not self.db:
            return

        # Resolve sentiment if not pre-computed
        if sentiment is None:
            result = self.analyze(text)
            sentiment = result.get("sentiment", "neutral")

        try:
            # Import lazily to avoid circular imports
            from ..models.sentiment_log import SentimentLog  # type: ignore[import]

            label_map = {
                "positive": SentimentLabel.positive,
                "neutral": SentimentLabel.neutral,
                "negative": SentimentLabel.negative,
            }
            log_entry = SentimentLog(
                user_id=user_id,
                score=1.0 if sentiment == "positive" else (-1.0 if sentiment == "negative" else 0.0),
                sentiment=label_map.get(sentiment, SentimentLabel.neutral),
            )
            self.db.add(log_entry)
            self.db.commit()
        except ImportError:
            # Model not yet created — log to application log only
            logger.info(f"sentiment_log model unavailable; skipped DB write for user {user_id}: {sentiment}")
        except Exception as exc:
            self.db.rollback()
            logger.warning(f"Failed to persist sentiment log: {exc}")

    def analyze_and_log(self, user_id: UUID, text: str) -> Dict:
        """Analyze text sentiment and persist the result. Returns the analysis dict."""
        result = self.analyze(text)
        self.log_sentiment(user_id=user_id, text=text, sentiment=result.get("sentiment"))
        return result
