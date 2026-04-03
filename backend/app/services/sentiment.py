from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

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
        # In production, query database for actual sentiment history
        # For now, return mock data demonstrating the expected structure
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # In production: Query sentiment history from DB
        # Example query:
        # query = self.db.query(SentimentHistory)
        # if user_id:
        #     query = query.filter(SentimentHistory.user_id == user_id)
        #     query = query.filter(SentimentHistory.created_at >= start_date)
        
        # Mock response for demonstration
        return {
            "average_sentiment": 0.3,
            "trend": "stable",
            "positive_percentage": 60,
            "negative_percentage": 15,
            "neutral_percentage": 25,
            "total_analyses": 150,
            "period_days": days
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
