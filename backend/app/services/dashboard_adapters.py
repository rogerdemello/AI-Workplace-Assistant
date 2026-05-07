"""Typed adapter contracts for analytics dashboard payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from .dashboard_analytics import (
    build_ai_summary,
    compute_kpi_overview,
    compute_weekly_quality,
    detect_manager_issue_pattern,
    employee_insights_for_hr,
    employee_insights_for_manager,
    sentiment_analysis_source_drift,
    sentiment_trend_days,
)


class KpiOverviewContract(BaseModel):
    engagement_score: float
    resolution_rate: float
    avg_response_time: float
    active_users: int
    total_tickets: int
    open_tickets: int
    enps: float = 0.0


class SentimentTrendContract(BaseModel):
    date: str
    positive: float
    neutral: float
    negative: float


class EmployeeInsightContract(BaseModel):
    id: str
    employee_id: str
    name: str
    sentiment_score: int
    risk_score: int
    last_active: str
    department: str
    mental_health_score: Optional[int] = None
    risk_confidence: Optional[float] = None
    risk_calibration_band: Optional[str] = None
    risk_top_factors: Optional[List[str]] = None
    trend: str = "stable"
    delta: int = 0
    risk_label: str = "Low"
    short_term_trend: Optional[float] = None
    long_term_trend: Optional[float] = None
    spike_alert: bool = False
    top_topic: Optional[str] = None
    top_emotion: Optional[str] = None
    sentiment_last_updated_at: Optional[str] = None
    sentiment_confidence: Optional[float] = None
    sentiment_confidence_band: Optional[str] = None
    complaints_5d: int = 0
    silent_risk: bool = False
    sustained_risk_pattern: bool = False
    negative_turns_in_window: int = 0
    narrative: Optional[List[str]] = None


class WeeklyQualityContract(BaseModel):
    window_days: int
    feedback_responses: int
    avg_csat: float
    helpful_rate: float
    detractor_rate: float
    avg_first_response_seconds: float
    conversations_measured: int
    quality_label: str


class SentimentSourceDriftContract(BaseModel):
    window_days: int
    total: int
    by_source: Dict[str, int]
    pct_by_source: Dict[str, float]


class DashboardBundleContract(BaseModel):
    metrics: KpiOverviewContract
    sentiment: List[SentimentTrendContract]
    employees: List[EmployeeInsightContract]
    weekly_quality: WeeklyQualityContract
    ai_summary: str
    manager_pattern: Optional[Dict[str, Any]] = None
    sentiment_stale_days: int = 7
    sustained_risk_window_days: int = 7
    sustained_risk_min_negative_turns: int = 3
    sentiment_source_drift: SentimentSourceDriftContract
    last_chat_sentiment_at: Optional[datetime] = None


def build_dashboard_bundle_contract(
    db: Session,
    *,
    days: int = 14,
    employee_limit: int = 50,
    drift_days: int = 7,
) -> DashboardBundleContract:
    metrics_dict = compute_kpi_overview(db)
    drift_raw = sentiment_analysis_source_drift(db, days=max(1, min(int(drift_days), 90)))

    # Freshness: when was the most recent chat sentiment processed?
    from ..models.sentiment_log import SentimentLog
    last_log = (
        db.query(SentimentLog.created_at)
        .order_by(SentimentLog.created_at.desc())
        .first()
    )
    last_chat_sentiment_at = last_log[0] if last_log else None

    return DashboardBundleContract(
        metrics=KpiOverviewContract(**metrics_dict),
        sentiment=[SentimentTrendContract(**row) for row in sentiment_trend_days(db, days=days)],
        employees=[EmployeeInsightContract(**row) for row in employee_insights_for_hr(db, limit=employee_limit)],
        weekly_quality=WeeklyQualityContract(**compute_weekly_quality(db, window_days=7)),
        ai_summary=build_ai_summary(db, open_tickets=metrics_dict["open_tickets"]),
        manager_pattern=detect_manager_issue_pattern(db),
        sentiment_stale_days=max(1, int(settings.SENTIMENT_STALE_DAYS)),
        sustained_risk_window_days=max(1, int(settings.SUSTAINED_NEGATIVE_WINDOW_DAYS)),
        sustained_risk_min_negative_turns=max(1, int(settings.SUSTAINED_NEGATIVE_MIN_MESSAGES)),
        sentiment_source_drift=SentimentSourceDriftContract(**drift_raw),
        last_chat_sentiment_at=last_chat_sentiment_at,
    )


def build_kpi_overview_contract(db: Session) -> KpiOverviewContract:
    return KpiOverviewContract(**compute_kpi_overview(db))


def build_sentiment_trend_contracts(db: Session, *, days: int = 14) -> List[SentimentTrendContract]:
    return [SentimentTrendContract(**row) for row in sentiment_trend_days(db, days=days)]


def build_employee_insight_contracts(db: Session, *, limit: int = 50) -> List[EmployeeInsightContract]:
    return [EmployeeInsightContract(**row) for row in employee_insights_for_hr(db, limit=limit)]


def build_manager_team_bundle_contract(
    db: Session,
    *,
    manager_id,
    limit: int = 50,
) -> Dict[str, Any]:
    employees = [EmployeeInsightContract(**row) for row in employee_insights_for_manager(db, manager_id=manager_id, limit=limit)]
    team_size = len(employees)
    if team_size == 0:
        return {
            "manager_id": str(manager_id),
            "team_size": 0,
            "avg_team_sentiment": 0.0,
            "avg_team_risk": 0.0,
            "high_risk_count": 0,
            "open_complaints": 0,
            "employees": [],
        }

    avg_sentiment = round(sum(int(e.sentiment_score) for e in employees) / team_size, 1)
    avg_risk = round(sum(int(e.risk_score) for e in employees) / team_size, 1)
    high_risk = sum(1 for e in employees if int(e.risk_score) >= 70)
    open_complaints = sum(int(getattr(e, "complaints_5d", 0) or 0) for e in employees)
    return {
        "manager_id": str(manager_id),
        "team_size": team_size,
        "avg_team_sentiment": avg_sentiment,
        "avg_team_risk": avg_risk,
        "high_risk_count": high_risk,
        "open_complaints": open_complaints,
        "employees": [e.model_dump() for e in employees],
    }

