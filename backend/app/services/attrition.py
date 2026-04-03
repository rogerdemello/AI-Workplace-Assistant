from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AttritionRiskService:
    """
    Attrition risk analysis service for HR assistant.
    
    Supports:
    - Risk score calculation based on multiple factors
    - Risk level classification (low/medium/high)
    - Risk history tracking
    - Risk factor breakdown analysis
    
    In production, this would integrate with database queries and ML models.
    """
    
    # Risk thresholds
    LOW_THRESHOLD = 0.4
    HIGH_THRESHOLD = 0.6
    
    def __init__(self, db: Optional[object] = None):
        self.db = db
    
    def _calculate_risk_level(self, risk_score: float) -> str:
        """Convert numeric risk score to risk level."""
        if risk_score < self.LOW_THRESHOLD:
            return RiskLevel.LOW.value
        elif risk_score < self.HIGH_THRESHOLD:
            return RiskLevel.MEDIUM.value
        return RiskLevel.HIGH.value
    
    def calculate_risk(self, user_id: UUID) -> Dict:
        """
        Calculate attrition risk for a specific user.
        
        Args:
            user_id: The UUID of the user to analyze
            
        Returns:
            Dict containing risk score, level, factors, and history
        """
        # In production, this would query actual user data:
        # - Sentiment history from conversations
        # - Engagement metrics
        # - Ticket history and sentiment
        # - Response patterns
        
        # Mock implementation based on expected output format
        # In production, calculate from actual data
        
        return {
            "user_id": str(user_id),
            "risk_score": 0.72,
            "risk_level": "high",
            "factors": [
                {
                    "name": "sentiment_trend",
                    "contribution": 0.35,
                    "description": "Declining sentiment over 30 days"
                },
                {
                    "name": "ticket_sentiment",
                    "contribution": 0.25,
                    "description": "Negative sentiment in recent tickets"
                },
                {
                    "name": "engagement_score",
                    "contribution": 0.20,
                    "description": "Low engagement score"
                },
                {
                    "name": "response_patterns",
                    "contribution": 0.20,
                    "description": "Reduced interaction frequency"
                }
            ],
            "history": [
                {"date": "2026-03-01", "risk_score": 0.45, "risk_level": "low"},
                {"date": "2026-02-01", "risk_score": 0.55, "risk_level": "medium"},
                {"date": "2026-01-01", "risk_score": 0.72, "risk_level": "high"}
            ]
        }
    
    def calculate_risk_from_data(
        self,
        sentiment_trend: float,
        ticket_sentiment: float,
        engagement_score: float,
        response_frequency: float
    ) -> Dict:
        """
        Calculate risk score from individual factors.
        
        Args:
            sentiment_trend: Trend of sentiment over time (0-1, higher = worse)
            ticket_sentiment: Average sentiment in tickets (0-1, higher = worse)
            engagement_score: User engagement level (0-1, higher = better)
            response_frequency: Frequency of user responses (0-1, higher = better)
            
        Returns:
            Dict with calculated risk score and breakdown
        """
        # Weight each factor
        weights = {
            "sentiment_trend": 0.35,
            "ticket_sentiment": 0.25,
            "engagement_score": 0.20,
            "response_frequency": 0.20
        }
        
        # Calculate contribution (invert engagement and frequency so higher = worse)
        contributions = {
            "sentiment_trend": sentiment_trend * weights["sentiment_trend"],
            "ticket_sentiment": ticket_sentiment * weights["ticket_sentiment"],
            "engagement_score": (1 - engagement_score) * weights["engagement_score"],
            "response_frequency": (1 - response_frequency) * weights["response_frequency"]
        }
        
        # Calculate total risk score
        risk_score = sum(contributions.values())
        risk_score = min(max(risk_score, 0.0), 1.0)  # Clamp to 0-1
        
        risk_level = self._calculate_risk_level(risk_score)
        
        return {
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "factors": [
                {
                    "name": "sentiment_trend",
                    "contribution": round(contributions["sentiment_trend"], 3),
                    "description": "Declining sentiment over 30 days"
                },
                {
                    "name": "ticket_sentiment",
                    "contribution": round(contributions["ticket_sentiment"], 3),
                    "description": "Negative sentiment in recent tickets"
                },
                {
                    "name": "engagement_score",
                    "contribution": round(contributions["engagement_score"], 3),
                    "description": "Low engagement score"
                },
                {
                    "name": "response_patterns",
                    "contribution": round(contributions["response_frequency"], 3),
                    "description": "Reduced interaction frequency"
                }
            ]
        }
    
    def get_department_risk_summary(self, department_id: Optional[UUID] = None) -> Dict:
        """
        Get attrition risk summary for a department or entire organization.
        
        Args:
            department_id: Optional UUID to filter by department
            
        Returns:
            Dict with risk scores for all users and average risk
        """
        # In production, query database for actual user data
        # For now, return mock data
        
        risk_scores = [
            {
                "user_id": "1",
                "name": "John Doe",
                "risk_score": 0.72,
                "risk_level": "high"
            },
            {
                "user_id": "2",
                "name": "Jane Smith",
                "risk_score": 0.45,
                "risk_level": "low"
            },
            {
                "user_id": "3",
                "name": "Bob Johnson",
                "risk_score": 0.55,
                "risk_level": "medium"
            }
        ]
        
        # Calculate average risk
        average_risk = sum(r["risk_score"] for r in risk_scores) / len(risk_scores)
        
        return {
            "risk_scores": risk_scores,
            "average_risk": round(average_risk, 2)
        }
    
    def get_risk_history(self, user_id: UUID, months: int = 3) -> List[Dict]:
        """
        Get historical risk data for a user.
        
        Args:
            user_id: The UUID of the user
            months: Number of months of history to retrieve
            
        Returns:
            List of historical risk records
        """
        # In production, query database for actual history
        # For now, return mock data
        
        history = []
        base_date = datetime.utcnow()
        
        for i in range(months):
            date = base_date - timedelta(days=30 * (months - i - 1))
            risk_score = 0.45 + (i * 0.10)  # Progressive increase
            risk_level = self._calculate_risk_level(risk_score)
            
            history.append({
                "date": date.strftime("%Y-%m-%d"),
                "risk_score": round(risk_score, 2),
                "risk_level": risk_level
            })
        
        return history


def get_attrition_risk_service(db: Optional[object] = None) -> AttritionRiskService:
    """Factory function to get AttritionRiskService instance."""
    return AttritionRiskService(db=db)
