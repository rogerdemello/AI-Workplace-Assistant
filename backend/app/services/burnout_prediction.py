from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from enum import Enum
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.conversation import Conversation, Message, MessageSender, SentimentLabel
from ..core.time import utcnow_naive
from ..models.user import User, UserRole, UserStatus

logger = logging.getLogger(__name__)


class BurnoutRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BurnoutPredictionService:
    """Burnout risk prediction service for HR assistant.

    Predicts burnout risk based on:
    - Sentiment trend analysis
    - Leave pattern analysis
    - Engagement decline patterns
    - Ticket sentiment patterns
    - Workload indicators
    """

    LOW_THRESHOLD = 0.25
    MEDIUM_THRESHOLD = 0.50
    HIGH_THRESHOLD = 0.75

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def _window_boundaries(self, start_dt: Optional[datetime], end_dt: Optional[datetime], days: int = 30) -> tuple[datetime, datetime]:
        end = end_dt or utcnow_naive()
        start = start_dt or (end - timedelta(days=days))
        return start, end

    def _base_query_filters(self, user_id: UUID, start_dt: datetime, end_dt: datetime):
        return [Conversation.user_id == user_id, Message.created_at >= start_dt, Message.created_at <= end_dt]

    def _calculate_sentiment_factor(
        self,
        user_id: UUID,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> float:
        if not self.db:
            return 0.5

        start, end = self._window_boundaries(start_dt, end_dt, days=30)

        rows = (
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
            SentimentLabel.positive: 0.1,
            SentimentLabel.neutral: 0.5,
            SentimentLabel.negative: 0.9,
        }
        if not rows:
            return 0.5

        values = [sentiment_weights.get(row[0], 0.5) for row in rows]
        return sum(values) / len(values)

    def _calculate_engagement_factor(
        self,
        user_id: UUID,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> float:
        if not self.db:
            return 0.5

        start, end = self._window_boundaries(start_dt, end_dt, days=30)
        previous_start = start - timedelta(days=30)
        previous_end = start

        current_messages = (
            self.db.query(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                *self._base_query_filters(user_id, start, end),
                Message.sender == MessageSender.user,
            )
            .scalar()
            or 0
        )

        previous_messages = (
            self.db.query(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                *self._base_query_filters(user_id, previous_start, previous_end),
                Message.sender == MessageSender.user,
            )
            .scalar()
            or 0
        )

        if previous_messages == 0:
            return 0.5 if current_messages == 0 else 0.3

        decline_ratio = current_messages / previous_messages
        if decline_ratio >= 1.0:
            return 0.1
        elif decline_ratio >= 0.7:
            return 0.3
        elif decline_ratio >= 0.5:
            return 0.6
        else:
            return 0.9

    def _calculate_leave_pattern_factor(
        self,
        user_id: UUID,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> float:
        if not self.db:
            return 0.3

        start, end = self._window_boundaries(start_dt, end_dt, days=60)

        leave_count = (
            self.db.query(func.count(func.distinct(Message.id)))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                *self._base_query_filters(user_id, start, end),
                Message.sender == MessageSender.user,
                Message.message_text.ilike("%leave%"),
            )
            .scalar()
            or 0
        )

        if leave_count <= 2:
            return 0.1
        elif leave_count <= 5:
            return 0.3
        elif leave_count <= 10:
            return 0.6
        else:
            return 0.9

    def _calculate_ticket_stress_factor(
        self,
        user_id: UUID,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> float:
        if not self.db:
            return 0.3

        start, end = self._window_boundaries(start_dt, end_dt, days=30)

        from ..models.ticket import Ticket, TicketStatus

        open_tickets = (
            self.db.query(func.count(Ticket.id))
            .filter(
                Ticket.user_id == user_id,
                Ticket.created_at >= start,
                Ticket.created_at <= end,
                Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]),
            )
            .scalar()
            or 0
        )

        if open_tickets == 0:
            return 0.1
        elif open_tickets <= 2:
            return 0.3
        elif open_tickets <= 5:
            return 0.6
        else:
            return 0.9

    def _calculate_workload_factor(
        self,
        user_id: UUID,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> float:
        if not self.db:
            return 0.3

        start, end = self._window_boundaries(start_dt, end_dt, days=30)

        message_count = (
            self.db.query(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                *self._base_query_filters(user_id, start, end),
                Message.sender == MessageSender.user,
            )
            .scalar()
            or 0
        )

        if message_count <= 10:
            return 0.1
        elif message_count <= 30:
            return 0.3
        elif message_count <= 60:
            return 0.6
        else:
            return 0.9

    def _compute_all_factors(
        self,
        user_id: UUID,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> Dict[str, float]:
        return {
            "sentiment_trend": self._calculate_sentiment_factor(user_id, start_dt, end_dt),
            "engagement_decline": self._calculate_engagement_factor(user_id, start_dt, end_dt),
            "leave_patterns": self._calculate_leave_pattern_factor(user_id, start_dt, end_dt),
            "ticket_stress": self._calculate_ticket_stress_factor(user_id, start_dt, end_dt),
            "workload": self._calculate_workload_factor(user_id, start_dt, end_dt),
        }

    def _calculate_risk_level(self, risk_score: float) -> str:
        if risk_score < self.LOW_THRESHOLD:
            return BurnoutRiskLevel.LOW.value
        elif risk_score < self.MEDIUM_THRESHOLD:
            return BurnoutRiskLevel.MEDIUM.value
        elif risk_score < self.HIGH_THRESHOLD:
            return BurnoutRiskLevel.HIGH.value
        return BurnoutRiskLevel.CRITICAL.value

    def _calculate_risk_score(
        self,
        sentiment_trend: float,
        engagement_decline: float,
        leave_patterns: float,
        ticket_stress: float,
        workload: float,
    ) -> float:
        weights = {
            "sentiment_trend": 0.30,
            "engagement_decline": 0.25,
            "leave_patterns": 0.15,
            "ticket_stress": 0.15,
            "workload": 0.15,
        }

        score = (
            sentiment_trend * weights["sentiment_trend"]
            + engagement_decline * weights["engagement_decline"]
            + leave_patterns * weights["leave_patterns"]
            + ticket_stress * weights["ticket_stress"]
            + workload * weights["workload"]
        )

        return min(max(score, 0.0), 1.0)

    def calculate_risk(self, user_id: UUID) -> Dict:
        factors = self._compute_all_factors(user_id=user_id)
        score = self._calculate_risk_score(**factors)

        return {
            "user_id": str(user_id),
            "risk_score": round(score, 2),
            "risk_level": self._calculate_risk_level(score),
            "factors": factors,
            "confidence": 0.75,
            "assessed_at": utcnow_naive().isoformat(),
        }

    def calculate_risk_from_data(
        self,
        sentiment_trend: float,
        engagement_decline: float,
        leave_patterns: float,
        ticket_stress: float,
        workload: float,
    ) -> Dict:
        score = self._calculate_risk_score(
            sentiment_trend,
            engagement_decline,
            leave_patterns,
            ticket_stress,
            workload,
        )

        risk_level = self._calculate_risk_level(score)

        return {
            "risk_score": round(score, 2),
            "risk_level": risk_level,
            "factors": {
                "sentiment_trend": sentiment_trend,
                "engagement_decline": engagement_decline,
                "leave_patterns": leave_patterns,
                "ticket_stress": ticket_stress,
                "workload": workload,
            },
            "confidence": 0.75,
        }

    def get_department_risk_summary(self, department_id: Optional[UUID] = None) -> Dict:
        if not self.db:
            return {"risk_scores": [], "average_risk": 0.0}

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
            return {"risk_scores": [], "average_risk": 0.0}

        risk_scores.sort(key=lambda row: row["risk_score"], reverse=True)
        average_risk = sum(r["risk_score"] for r in risk_scores) / len(risk_scores)

        return {
            "risk_scores": risk_scores,
            "average_risk": round(average_risk, 2),
            "high_risk_count": sum(1 for r in risk_scores if r["risk_level"] in ["high", "critical"]),
            "medium_risk_count": sum(1 for r in risk_scores if r["risk_level"] == "medium"),
        }

    def get_risk_history(self, user_id: UUID, months: int = 3) -> List[Dict]:
        history = []
        now = utcnow_naive()

        for i in range(months):
            window_end = now - timedelta(days=30 * (months - i - 1))
            window_start = window_end - timedelta(days=30)

            factors = self._compute_all_factors(user_id=user_id, start_dt=window_start, end_dt=window_end)
            score = self._calculate_risk_score(**factors)

            history.append(
                {
                    "date": window_end.strftime("%Y-%m-%d"),
                    "risk_score": round(score, 2),
                    "risk_level": self._calculate_risk_level(score),
                }
            )

        return history


def get_burnout_prediction_service(db: Optional[Session] = None) -> BurnoutPredictionService:
    return BurnoutPredictionService(db=db)