"""
Employee-level intelligence aggregates (dashboards, risk, trends).

Delegates to SentimentPipelineService for the canonical 7d/30d blend and risk model.
"""

from __future__ import annotations

import logging
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from ..sentiment_pipeline import SentimentPipelineService
from ...models.employee_score import EmployeeScore

logger = logging.getLogger(__name__)


class EmployeeIntelligenceService:
    """Facade for HR dashboard aggregates (sentiment_score, trend, risk, engagement)."""

    def __init__(self, db: Session):
        self._db = db
        self._pipeline = SentimentPipelineService(db)

    def refresh_employee_aggregate(self, employee_id: UUID) -> EmployeeScore:
        """Recompute employee_scores from sentiment_logs (+ signals)."""
        return self._pipeline.refresh_employee_aggregate(employee_id)

    def evaluate_alert_signals(self, row: EmployeeScore) -> List[str]:
        """Lightweight rule hooks — pair with HR notifications / webhooks later."""
        alerts: List[str] = []
        if row.sentiment_score < 40:
            alerts.append("high_risk_sentiment")
        if row.trend_delta <= -20:
            alerts.append("sentiment_drop_sharp")
        if row.risk_score >= 70:
            alerts.append("elevated_risk_score")
        if alerts:
            logger.info(
                "HR intelligence signals for %s: %s",
                row.employee_id,
                ",".join(alerts),
            )
        return alerts
