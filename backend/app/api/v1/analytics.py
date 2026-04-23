from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ...auth import require_roles
from ...database import get_db
from ...services.dashboard_analytics import (
    build_ai_summary,
    compute_weekly_quality,
    compute_kpi_overview,
    employee_insights_for_hr,
    sentiment_trend_days,
)
from ...services.analytics import get_realtime_analytics_snapshot
from ...models.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


class KPIResponse(BaseModel):
    engagement_score: float
    resolution_rate: float
    avg_response_time: float
    active_users: int
    total_tickets: int
    open_tickets: int
    enps: float = 0.0


class SentimentTrendResponse(BaseModel):
    date: str
    positive: float
    neutral: float
    negative: float


class EmployeeInsightResponse(BaseModel):
    id: str
    employee_id: str
    name: str
    sentiment_score: int
    risk_score: int
    last_active: str
    department: str
    mental_health_score: Optional[int] = None


class WeeklyQualityResponse(BaseModel):
    window_days: int
    feedback_responses: int
    avg_csat: float
    helpful_rate: float
    detractor_rate: float
    avg_first_response_seconds: float
    conversations_measured: int
    quality_label: str


class DashboardBundleResponse(BaseModel):
    """Single call for Next.js HR dashboard (reduces round trips)."""
    metrics: KPIResponse
    sentiment: List[SentimentTrendResponse]
    employees: List[EmployeeInsightResponse]
    weekly_quality: WeeklyQualityResponse
    ai_summary: str


@router.get("/overview", response_model=KPIResponse)
def get_overview(
    department_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    del department_id  # reserved for future filter
    data = compute_kpi_overview(db)
    return KPIResponse(**data)


@router.get("/sentiment", response_model=List[SentimentTrendResponse])
def get_sentiment_trend(
    days: int = Query(default=14, le=90),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    rows = sentiment_trend_days(db, days=days)
    return [SentimentTrendResponse(**r) for r in rows]


@router.get("/employees", response_model=List[EmployeeInsightResponse])
def get_employee_insights(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    rows = employee_insights_for_hr(db, limit=limit)
    return [EmployeeInsightResponse(**r) for r in rows]


@router.get("/dashboard", response_model=DashboardBundleResponse)
def get_hr_dashboard_bundle(
    days: int = Query(default=14, le=90),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    metrics_dict = compute_kpi_overview(db)
    metrics = KPIResponse(**metrics_dict)
    sentiment = [SentimentTrendResponse(**r) for r in sentiment_trend_days(db, days=days)]
    employees = [EmployeeInsightResponse(**r) for r in employee_insights_for_hr(db, limit=50)]
    weekly_quality = WeeklyQualityResponse(**compute_weekly_quality(db, window_days=7))
    ai_summary = build_ai_summary(db, open_tickets=metrics_dict["open_tickets"])
    return DashboardBundleResponse(
        metrics=metrics,
        sentiment=sentiment,
        employees=employees,
        weekly_quality=weekly_quality,
        ai_summary=ai_summary,
    )


@router.get("/resolution")
def get_resolution_metrics(
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    data = compute_kpi_overview(db)
    total = data["total_tickets"]
    resolved_rate = data["resolution_rate"]
    return {
        "total_resolved": int(total * resolved_rate) if total else 0,
        "total_tickets": total,
        "resolution_rate": resolved_rate,
        "by_priority": {"critical": 0.0, "high": 0.0, "medium": resolved_rate, "low": 0.0},
    }


@router.get("/realtime")
def get_realtime_metrics(
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Event-driven counters for near-real-time dashboard updates."""
    return get_realtime_analytics_snapshot()


class AttritionRiskResponse(BaseModel):
    user_id: str
    name: str
    risk_score: float
    risk_level: str


class AttritionSummaryResponse(BaseModel):
    risk_scores: List[AttritionRiskResponse]
    average_risk: float


class BurnoutRiskResponse(BaseModel):
    user_id: str
    name: str
    risk_score: float
    risk_level: str
    factors: dict


class BurnoutSummaryResponse(BaseModel):
    risk_scores: List[BurnoutRiskResponse]
    average_risk: float
    high_risk_count: int
    medium_risk_count: int


class ExecutiveDashboardResponse(BaseModel):
    org_health_score: float
    burnout_risk_pct: float
    attrition_risk_pct: float
    enps: float
    engagement_trend: List[dict]
    top_risks: List[dict]
    recommendations: List[str]


class InsightResponse(BaseModel):
    id: str
    insight_type: str
    title: str
    description: str
    severity: str
    affected_entity_type: Optional[str]
    affected_entity_id: Optional[str]
    metrics: dict
    recommendations: List[str]
    is_resolved: bool
    created_at: str


@router.get("/attrition", response_model=AttritionSummaryResponse)
def get_attrition_risk(
    department_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(["admin"])),
):
    """Get attrition risk analysis for users."""
    from ...services.attrition import AttritionRiskService

    service = AttritionRiskService(db=db)
    result = service.get_department_risk_summary(department_id)

    return result


@router.get("/burnout", response_model=BurnoutSummaryResponse)
def get_burnout_risk(
    department_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Get burnout risk analysis for users."""
    from ...services.burnout_prediction import BurnoutPredictionService

    service = BurnoutPredictionService(db=db)
    result = service.get_department_risk_summary(department_id)

    return result


@router.get("/burnout/{user_id}", response_model=BurnoutRiskResponse)
def get_user_burnout_risk(
    user_id: UUID,
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Get burnout risk for a specific user."""
    from ...services.burnout_prediction import BurnoutPredictionService

    service = BurnoutPredictionService(db=db)
    result = service.calculate_risk(user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        result["name"] = user.name

    return result


@router.get("/executive", response_model=ExecutiveDashboardResponse)
def get_executive_dashboard(
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Get executive dashboard with org-wide analytics."""
    from ...services.burnout_prediction import BurnoutPredictionService
    from ...services.attrition import AttritionRiskService
    from ...services.sentiment import SentimentService
    from ...services.dashboard_analytics import compute_kpi_overview
    from ...core.time import utcnow_naive
    from datetime import timedelta

    kpi = compute_kpi_overview(db)
    burnout_service = BurnoutPredictionService(db=db)
    attrition_service = AttritionRiskService(db=db)
    sentiment_service = SentimentService(db=db)

    burnout_summary = burnout_service.get_department_risk_summary()
    attrition_summary = attrition_service.get_department_risk_summary()
    sentiment_trend = sentiment_service.get_trend(days=30)

    org_health_score = kpi["engagement_score"]
    burnout_risk_pct = (burnout_summary.get("high_risk_count", 0) / max(len(burnout_summary.get("risk_scores", [])), 1)) * 100
    attrition_risk_pct = (attrition_summary.get("average_risk", 0) * 100)

    now = utcnow_naive()
    engagement_trend = []
    for i in range(7):
        day = now - timedelta(days=6-i)
        engagement_trend.append({
            "date": day.strftime("%Y-%m-%d"),
            "score": org_health_score,
        })

    top_risks = []
    for risk in burnout_summary.get("risk_scores", [])[:5]:
        if risk.get("risk_level") in ["high", "critical"]:
            top_risks.append({
                "type": "burnout",
                "user_id": risk.get("user_id"),
                "name": risk.get("name"),
                "risk_score": risk.get("risk_score"),
            })

    recommendations = []
    if burnout_risk_pct > 20:
        recommendations.append("Schedule team wellness check-ins")
    if attrition_risk_pct > 30:
        recommendations.append("Review retention strategies for high-risk employees")
    if sentiment_trend.get("trend") == "declining":
        recommendations.append("Investigate recent sentiment declining factors")

    return {
        "org_health_score": org_health_score,
        "burnout_risk_pct": round(burnout_risk_pct, 1),
        "attrition_risk_pct": round(attrition_risk_pct, 1),
        "enps": kpi.get("enps", 0),
        "engagement_trend": engagement_trend,
        "top_risks": top_risks,
        "recommendations": recommendations,
    }


@router.get("/insights", response_model=List[InsightResponse])
def get_insights(
    limit: int = Query(default=20, le=100),
    include_resolved: bool = Query(default=False),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Get AI-generated insights."""
    from sqlalchemy import text

    query_sql = "SELECT id, insight_type, title, description, severity, affected_entity_type, affected_entity_id, metrics, recommendations, is_resolved, created_at FROM insights"
    if not include_resolved:
        query_sql += " WHERE is_resolved = false"
    query_sql += " ORDER BY created_at DESC LIMIT :limit"
    
    result = db.execute(text(query_sql), {"limit": limit})
    
    return [
        InsightResponse(
            id=str(row[0]),
            insight_type=row[1] or "",
            title=row[2] or "",
            description=row[3] or "",
            severity=row[4] or "info",
            affected_entity_type=row[5],
            affected_entity_id=str(row[6]) if row[6] else None,
            metrics=row[7] if row[7] else {},
            recommendations=row[8] if row[8] else [],
            is_resolved=bool(row[9]),
            created_at=str(row[10]),
        )
        for row in result.fetchall()
    ]
