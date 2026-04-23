from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime, timedelta
from enum import Enum
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.conversation import Conversation, Message, MessageSender, SentimentLabel
from ..core.time import utcnow_naive
from ..models.ticket import Ticket, TicketStatus
from ..models.user import User, UserRole, UserStatus

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
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def _window_boundaries(self, start_dt: Optional[datetime], end_dt: Optional[datetime], days: int = 30) -> tuple[datetime, datetime]:
        end = end_dt or utcnow_naive()
        start = start_dt or (end - timedelta(days=days))
        return start, end

    def _base_query_filters(self, user_id: UUID, start_dt: datetime, end_dt: datetime):
        return [Conversation.user_id == user_id, Message.created_at >= start_dt, Message.created_at <= end_dt]

    def _compute_window_factors(
        self,
        user_id: UUID,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Compute normalized factor values in [0,1] for attrition scoring."""
        if not self.db:
            return {
                "sentiment_trend": 0.5,
                "ticket_sentiment": 0.5,
                "engagement_score": 0.5,
                "response_frequency": 0.5,
            }

        start, end = self._window_boundaries(start_dt, end_dt)

        sentiment_rows = (
            self.db.query(Message.sentiment)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                *self._base_query_filters(user_id, start, end),
                Message.sender == MessageSender.user,
                Message.sentiment.isnot(None),
            )
            .all()
        )

        sentiment_weights = {
            SentimentLabel.positive: 0.15,
            SentimentLabel.neutral: 0.5,
            SentimentLabel.negative: 0.9,
        }
        if sentiment_rows:
            sentiment_values = [
                sentiment_weights.get(row[0], 0.5)
                for row in sentiment_rows
            ]
            sentiment_trend = sum(sentiment_values) / len(sentiment_values)
        else:
            sentiment_trend = 0.5

        total_messages = (
            self.db.query(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(*self._base_query_filters(user_id, start, end), Message.sender == MessageSender.user)
            .scalar()
            or 0
        )
        total_conversations = (
            self.db.query(func.count(func.distinct(Conversation.id)))
            .join(Message, Message.conversation_id == Conversation.id)
            .filter(*self._base_query_filters(user_id, start, end), Message.sender == MessageSender.user)
            .scalar()
            or 0
        )

        message_engagement = min(1.0, float(total_messages) / 20.0)
        conversation_engagement = min(1.0, float(total_conversations) / 8.0)
        engagement_score = (message_engagement + conversation_engagement) / 2.0

        last_message_at = (
            self.db.query(func.max(Message.created_at))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == user_id, Message.sender == MessageSender.user)
            .scalar()
        )
        if not last_message_at:
            response_frequency = 0.0
        else:
            silence_days = max(0.0, (end - last_message_at).total_seconds() / 86400.0)
            response_frequency = max(0.0, 1.0 - min(1.0, silence_days / 30.0))

        open_tickets = (
            self.db.query(func.count(Ticket.id))
            .filter(
                Ticket.user_id == user_id,
                Ticket.created_at <= end,
                Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]),
            )
            .scalar()
            or 0
        )
        escalated_tickets = (
            self.db.query(func.count(Ticket.id))
            .filter(
                Ticket.user_id == user_id,
                Ticket.created_at <= end,
                Ticket.status == TicketStatus.escalated,
            )
            .scalar()
            or 0
        )

        ticket_sentiment = min(1.0, (open_tickets * 0.18) + (escalated_tickets * 0.35))

        return {
            "sentiment_trend": float(min(max(sentiment_trend, 0.0), 1.0)),
            "ticket_sentiment": float(min(max(ticket_sentiment, 0.0), 1.0)),
            "engagement_score": float(min(max(engagement_score, 0.0), 1.0)),
            "response_frequency": float(min(max(response_frequency, 0.0), 1.0)),
        }
    
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
        factors = self._compute_window_factors(user_id=user_id)
        score = self.calculate_risk_from_data(
            sentiment_trend=factors["sentiment_trend"],
            ticket_sentiment=factors["ticket_sentiment"],
            engagement_score=factors["engagement_score"],
            response_frequency=factors["response_frequency"],
        )

        return {
            "user_id": str(user_id),
            "risk_score": score["risk_score"],
            "risk_level": score["risk_level"],
            "factors": score["factors"],
            "history": self.get_risk_history(user_id=user_id, months=3),
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
        if not self.db:
            return {
                "risk_scores": [],
                "average_risk": 0.0,
            }

        query = self.db.query(User).filter(
            User.role == UserRole.employee,
            User.status == UserStatus.active,
        )

        if department_id is not None:
            query = query.filter(User.department_id == department_id)

        users = query.all()
        risk_scores = []

        for user in users:
            risk = self.calculate_risk(user.id)
            risk_scores.append(
                {
                    "user_id": str(user.id),
                    "name": user.name,
                    "risk_score": float(risk["risk_score"]),
                    "risk_level": risk["risk_level"],
                }
            )

        if not risk_scores:
            return {
                "risk_scores": [],
                "average_risk": 0.0,
            }

        risk_scores.sort(key=lambda row: row["risk_score"], reverse=True)
        average_risk = sum(r["risk_score"] for r in risk_scores) / len(risk_scores)

        return {
            "risk_scores": risk_scores,
            "average_risk": round(average_risk, 2),
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
        months = max(1, min(months, 12))
        history = []
        now = utcnow_naive()

        for i in range(months):
            # oldest -> newest
            window_end = now - timedelta(days=30 * (months - i - 1))
            window_start = window_end - timedelta(days=30)

            factors = self._compute_window_factors(user_id=user_id, start_dt=window_start, end_dt=window_end)
            score = self.calculate_risk_from_data(
                sentiment_trend=factors["sentiment_trend"],
                ticket_sentiment=factors["ticket_sentiment"],
                engagement_score=factors["engagement_score"],
                response_frequency=factors["response_frequency"],
            )

            history.append(
                {
                    "date": window_end.strftime("%Y-%m-%d"),
                    "risk_score": score["risk_score"],
                    "risk_level": score["risk_level"],
                }
            )

        return history


def get_attrition_risk_service(db: Optional[Session] = None) -> AttritionRiskService:
    """Factory function to get AttritionRiskService instance."""
    return AttritionRiskService(db=db)
