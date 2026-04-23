from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..models.user import User, UserRole, UserStatus
from ..models.department import Department
from ..models.conversation import Conversation, Message, MessageSender, SentimentLabel
from ..core.time import utcnow_naive

logger = logging.getLogger(__name__)


class InsightsEngine:
    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def _calculate_department_sentiment(
        self,
        department_id: UUID,
        days: int = 30,
    ) -> float:
        if not self.db:
            return 50.0

        from datetime import timedelta
        start_date = utcnow_naive() - timedelta(days=days)

        sql = text("""
            SELECT 
                COALESCE(
                    SUM(CASE WHEN m.sentiment = 'positive' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0),
                    50.0
                ) as score
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            JOIN users u ON c.user_id = u.id
            WHERE u.department_id = :dept_id
            AND m.sender = 'user'
            AND m.sentiment IS NOT NULL
            AND m.created_at >= :start_date
        """)

        result = self.db.execute(
            sql,
            {"dept_id": str(department_id), "start_date": start_date}
        ).fetchone()

        return float(result[0]) if result and result[0] else 50.0

    def _get_engagement_trend(
        self,
        department_id: Optional[UUID] = None,
        days: int = 30,
    ) -> str:
        if not self.db:
            return "stable"

        from datetime import timedelta
        now = utcnow_naive()
        start_current = now - timedelta(days=days)
        start_previous = start_current - timedelta(days=days)

        current_sql = text("""
            SELECT COUNT(DISTINCT c.id)
            FROM conversations c
            JOIN users u ON c.user_id = u.id
            WHERE c.started_at >= :start
            AND (:dept_id IS NULL OR u.department_id = :dept_id)
        """)

        current_count = self.db.execute(
            current_sql,
            {"start": start_current, "dept_id": str(department_id) if department_id else None}
        ).fetchone()[0] or 0

        previous_count = self.db.execute(
            current_sql,
            {"start": start_previous, "dept_id": str(department_id) if department_id else None}
        ).fetchone()[0] or 0

        if previous_count == 0:
            return "stable"

        change_pct = ((current_count - previous_count) / previous_count) * 100

        if change_pct > 10:
            return "improving"
        elif change_pct < -10:
            return "declining"
        return "stable"

    def generate_department_insights(
        self,
        department_id: Optional[UUID] = None,
    ) -> List[Dict]:
        insights = []
        if not self.db:
            return insights

        departments = []
        if department_id:
            dept = self.db.query(Department).filter(Department.id == department_id).first()
            if dept:
                departments.append(dept)
        else:
            departments = self.db.query(Department).all()

        for dept in departments:
            sentiment_score = self._calculate_department_sentiment(dept.id)
            engagement_trend = self._get_engagement_trend(dept.id)

            if sentiment_score < 40:
                insights.append({
                    "insight_type": "sentiment_decline",
                    "title": f"Mental health drop in {dept.name}",
                    "description": f"Department {dept.name} sentiment score dropped to {sentiment_score:.1f} (target: 60+)",
                    "severity": "warning",
                    "affected_entity_type": "department",
                    "affected_entity_id": str(dept.id),
                    "metrics": {
                        "sentiment_score": sentiment_score,
                        "target": 60.0,
                    },
                    "recommendations": [
                        "Schedule team check-in meeting",
                        "Review recent team changes",
                        "Consider team-building activities",
                    ],
                })
            elif sentiment_score < 50:
                insights.append({
                    "insight_type": "sentiment_warning",
                    "title": f"Attention needed in {dept.name}",
                    "description": f"Department {dept.name} at {sentiment_score:.1f} - monitor closely",
                    "severity": "info",
                    "affected_entity_type": "department",
                    "affected_entity_id": str(dept.id),
                    "metrics": {"sentiment_score": sentiment_score},
                    "recommendations": ["Continue monitoring", "Gather feedback informally"],
                })

            if engagement_trend == "declining":
                insights.append({
                    "insight_type": "engagement_decline",
                    "title": f"Activity declining in {dept.name}",
                    "description": f"Department {dept.name} showing reduced engagement",
                    "severity": "warning",
                    "affected_entity_type": "department",
                    "affected_entity_id": str(dept.id),
                    "metrics": {"trend": engagement_trend},
                    "recommendations": ["Analyze root causes", "Check for process issues"],
                })

        return insights

    def generate_org_insights(self) -> List[Dict]:
        insights = []
        if not self.db:
            return insights

        sql = text("""
            SELECT 
                u.department_id,
                COUNT(DISTINCT u.id) as user_count,
                COUNT(DISTINCT c.id) as conv_count,
                AVG(CASE m.sentiment 
                    WHEN 'positive' THEN 1.0
                    WHEN 'neutral' THEN 0.5
                    WHEN 'negative' THEN 0.0
                    ELSE 0.5
                END) as avg_sentiment
            FROM users u
            LEFT JOIN conversations c ON c.user_id = u.id
            LEFT JOIN messages m ON m.conversation_id = c.id AND m.sender = 'user'
            WHERE u.role = 'employee' AND u.status = 'active'
            AND c.started_at >= NOW() - INTERVAL '30 days'
            GROUP BY u.department_id
        """)

        result = self.db.execute(sql).fetchall()

        low_sentiment_depts = []
        for row in result:
            if row[3] and row[3] < 0.5:
                low_sentiment_depts.append((row[0], row[3]))

        if low_sentiment_depts:
            insights.append({
                "insight_type": "org_sentiment",
                "title": "Multiple departments below threshold",
                "description": f"{len(low_sentiment_depts)} department(s) showing low sentiment",
                "severity": "warning",
                "affected_entity_type": "organization",
                "affected_entity_id": None,
                "metrics": {
                    "dept_count": len(low_sentiment_depts),
                    "departments": [str(d[0]) for d in low_sentiment_depts],
                },
                "recommendations": [
                    "Conduct org-wide pulse survey",
                    "Review manager training programs",
                ],
            })

        return insights

    def generate_risk_based_insights(
        self,
        risk_threshold: float = 0.6,
    ) -> List[Dict]:
        insights = []
        if not self.db:
            return insights

        risk_sql = text("""
            SELECT risk_score FROM attrition_risk
            WHERE risk_score >= :threshold
            ORDER BY risk_score DESC
            LIMIT 10
        """)

        at_risk = self.db.execute(risk_sql, {"threshold": risk_threshold}).fetchall()

        if at_risk:
            insights.append({
                "insight_type": "high_attrition_risk",
                "title": "High attrition risk detected",
                "description": f"{len(at_risk)} employees at high risk",
                "severity": "critical",
                "affected_entity_type": "organization",
                "affected_entity_id": None,
                "metrics": {"count": len(at_risk), "threshold": risk_threshold},
                "recommendations": [
                    "Review retention strategies",
                    "Schedule 1:1 check-ins",
                    "Consider compensation review",
                ],
            })

        return insights

    def generate_all_insights(self) -> List[Dict]:
        all_insights = []

        all_insights.extend(self.generate_org_insights())
        all_insights.extend(self.generate_department_insights())
        all_insights.extend(self.generate_risk_based_insights())

        return all_insights


def get_insights_engine(db: Optional[Session] = None) -> InsightsEngine:
    return InsightsEngine(db=db)