from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ...auth import require_roles
from ...database import get_db
from ...services.dashboard_analytics import (
    compute_at_risk_count,
    compute_department_heatmap,
    compute_kpi_overview,
    compute_kpi_window,
    emotion_trend_days,
    emotion_trend_days_for_manager,
    employee_insights_for_manager,
    manager_effectiveness_for_hr,
    sentiment_analysis_source_drift,
    sentiment_source_drift_timeseries,
    sentiment_source_drift_timeseries_for_manager,
)
from ...services.dashboard_adapters import (
    build_dashboard_bundle_contract,
    build_employee_insight_contracts,
    build_kpi_overview_contract,
    build_manager_team_bundle_contract,
    build_sentiment_trend_contracts,
    EmployeeInsightContract,
    KpiOverviewContract,
    SentimentTrendContract,
    WeeklyQualityContract,
)
from ...services.analytics import get_realtime_analytics_snapshot
from ...models.user import User
from ...schemas.analytics import (
    KPIResponse,
    EmotionTrendResponse,
    SentimentSourceDriftResponse,
    SentimentSourceTrendResponse,
    SentimentTrendResponse,
    EmployeeInsightResponse,
    WeeklyQualityResponse,
    DashboardBundleResponse,
    AttritionRiskResponse,
    AttritionSummaryResponse,
    AttritionFactorResponse,
    AttritionUserRiskResponse,
    BurnoutRiskResponse,
    BurnoutSummaryResponse,
    ExecutiveDashboardResponse,
    InsightResponse,
    ManagerDashboardBundleResponse,
    ManagerEffectivenessResponse,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=KPIResponse)
def get_overview(
    department_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    del department_id  # reserved for future filter
    contract = build_kpi_overview_contract(db)
    return KPIResponse(**contract.model_dump())


@router.get("/sentiment", response_model=List[SentimentTrendResponse])
def get_sentiment_trend(
    days: int = Query(default=14, le=90),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    contracts = build_sentiment_trend_contracts(db, days=days)
    return [SentimentTrendResponse(**SentimentTrendContract.model_validate(row).model_dump()) for row in contracts]


@router.get("/emotions", response_model=List[EmotionTrendResponse])
def get_emotion_trend(
    days: int = Query(default=14, le=90),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    return [EmotionTrendResponse(**row) for row in emotion_trend_days(db, days=days)]


@router.get("/sentiment/source-drift", response_model=SentimentSourceDriftResponse)
def get_sentiment_source_drift(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Share of chat sentiment rows by classifier path (llm / lexicon / hybrid / provided) for drift monitoring."""
    payload = sentiment_analysis_source_drift(db, days=days)
    return SentimentSourceDriftResponse(**payload)


@router.get("/sentiment/source-drift/timeseries", response_model=List[SentimentSourceTrendResponse])
def get_sentiment_source_drift_timeseries(
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Daily % mix of classifier paths (same snapshot semantics as emotion trends)."""
    rows = sentiment_source_drift_timeseries(db, days=days)
    return [SentimentSourceTrendResponse(**row) for row in rows]


@router.get("/manager/emotions", response_model=List[EmotionTrendResponse])
def get_manager_emotion_trend(
    days: int = Query(default=14, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["manager"])),
):
    return [
        EmotionTrendResponse(**row)
        for row in emotion_trend_days_for_manager(db, manager_id=current_user.id, days=days)
    ]


@router.get("/manager/sentiment/source-drift/timeseries", response_model=List[SentimentSourceTrendResponse])
def get_manager_sentiment_source_drift_timeseries(
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["manager"])),
):
    """Classifier mix over time for direct reports only."""
    rows = sentiment_source_drift_timeseries_for_manager(db, current_user.id, days=days)
    return [SentimentSourceTrendResponse(**row) for row in rows]


@router.get("/employees", response_model=List[EmployeeInsightResponse])
def get_employee_insights(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    contracts = build_employee_insight_contracts(db, limit=limit)
    return [EmployeeInsightResponse(**EmployeeInsightContract.model_validate(row).model_dump()) for row in contracts]


@router.get("/dashboard", response_model=DashboardBundleResponse)
def get_hr_dashboard_bundle(
    days: int = Query(default=14, le=90),
    drift_days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    bundle = build_dashboard_bundle_contract(
        db, days=days, employee_limit=50, drift_days=drift_days
    )
    return DashboardBundleResponse(
        metrics=KPIResponse(**KpiOverviewContract.model_validate(bundle.metrics).model_dump()),
        sentiment=[
            SentimentTrendResponse(**SentimentTrendContract.model_validate(row).model_dump())
            for row in bundle.sentiment
        ],
        employees=[
            EmployeeInsightResponse(**EmployeeInsightContract.model_validate(row).model_dump())
            for row in bundle.employees
        ],
        weekly_quality=WeeklyQualityResponse(
            **WeeklyQualityContract.model_validate(bundle.weekly_quality).model_dump()
        ),
        ai_summary=bundle.ai_summary,
        manager_pattern=bundle.manager_pattern,
        sentiment_stale_days=bundle.sentiment_stale_days,
        sustained_risk_window_days=bundle.sustained_risk_window_days,
        sustained_risk_min_negative_turns=bundle.sustained_risk_min_negative_turns,
        sentiment_source_drift=SentimentSourceDriftResponse(**bundle.sentiment_source_drift.model_dump()),
        last_chat_sentiment_at=bundle.last_chat_sentiment_at,
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


@router.get("/attrition/{user_id}", response_model=AttritionUserRiskResponse)
def get_attrition_risk_for_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Explainable attrition risk for one employee."""
    from ...services.attrition import AttritionRiskService

    service = AttritionRiskService(db=db)
    result = service.calculate_risk(user_id)
    user = db.query(User).filter(User.id == user_id).first()
    result["name"] = user.name if user else "Employee"
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


@router.get("/manager-effectiveness", response_model=List[ManagerEffectivenessResponse])
def get_manager_effectiveness(
    limit: int = Query(default=25, le=200),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    rows = manager_effectiveness_for_hr(db=db, limit=limit)
    return [ManagerEffectivenessResponse(**row) for row in rows]


@router.get("/manager/team", response_model=List[EmployeeInsightResponse])
def get_manager_team_insights(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["manager"])),
):
    rows = employee_insights_for_manager(db=db, manager_id=current_user.id, limit=limit)
    return [EmployeeInsightResponse(**row) for row in rows]


@router.get("/manager/dashboard", response_model=ManagerDashboardBundleResponse)
def get_manager_dashboard_bundle(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["manager"])),
):
    payload = build_manager_team_bundle_contract(db=db, manager_id=current_user.id, limit=limit)
    return ManagerDashboardBundleResponse(**payload)


@router.get("/kpis-with-deltas")
def get_kpis_with_deltas(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """KPI tiles for the HR dashboard with deltas vs the prior equal-length window.

    Returns five metrics (avg_sentiment, active_employees, new_tickets,
    resolved_tickets, at_risk_count). The first four are flow metrics with a
    real prior-window comparison. ``at_risk_count`` is a current-state snapshot
    and therefore has no historical comparison (``previous`` and ``delta`` are
    null).
    """
    from datetime import timedelta
    from ...core.time import utcnow_naive

    now = utcnow_naive()
    current_since = now - timedelta(days=days)
    previous_since = now - timedelta(days=days * 2)

    current = compute_kpi_window(db, since=current_since, until=now)
    previous = compute_kpi_window(db, since=previous_since, until=current_since)

    def _delta(c, p):
        if c is None or p is None:
            return None
        return round(c - p, 2)

    at_risk = compute_at_risk_count(db)

    metrics = {
        "avg_sentiment": {
            "current": current["avg_sentiment"],
            "previous": previous["avg_sentiment"],
            "delta": _delta(current["avg_sentiment"], previous["avg_sentiment"]),
            "unit": "score",
        },
        "active_employees": {
            "current": current["active_employees"],
            "previous": previous["active_employees"],
            "delta": _delta(current["active_employees"], previous["active_employees"]),
            "unit": "count",
        },
        "new_tickets": {
            "current": current["new_tickets"],
            "previous": previous["new_tickets"],
            "delta": _delta(current["new_tickets"], previous["new_tickets"]),
            "unit": "count",
        },
        "resolved_tickets": {
            "current": current["resolved_tickets"],
            "previous": previous["resolved_tickets"],
            "delta": _delta(current["resolved_tickets"], previous["resolved_tickets"]),
            "unit": "count",
        },
        "at_risk_count": {
            "current": at_risk,
            "previous": None,
            "delta": None,
            "unit": "count",
        },
    }

    return {
        "window_days": days,
        "current_window": {"since": current_since.isoformat(), "until": now.isoformat()},
        "previous_window": {"since": previous_since.isoformat(), "until": current_since.isoformat()},
        "metrics": metrics,
    }


@router.get("/departments-heatmap")
def get_departments_heatmap(
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Department × sentiment bucket counts for the HR dashboard heatmap."""
    rows = compute_department_heatmap(db)
    return {"departments": rows}
