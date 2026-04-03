from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from ...auth import require_roles

router = APIRouter(prefix="/analytics", tags=["analytics"])


class KPIResponse(BaseModel):
    engagement_score: float
    resolution_rate: float
    avg_response_time: float
    active_users: int
    total_tickets: int


class SentimentTrendResponse(BaseModel):
    date: str
    positive: float
    neutral: float
    negative: float


@router.get("/overview", response_model=KPIResponse)
def get_overview(
    department_id: Optional[UUID] = None,
    current_user=Depends(require_roles(["hr", "admin"]))
):
    return {
        "engagement_score": 78.5,
        "resolution_rate": 0.85,
        "avg_response_time": 4.2,
        "active_users": 150,
        "total_tickets": 234
    }


@router.get("/sentiment", response_model=List[SentimentTrendResponse])
def get_sentiment_trend(
    days: int = Query(default=30, le=90),
    current_user=Depends(require_roles(["hr", "admin"]))
):
    trends = []
    for i in range(days):
        date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        trends.append({"date": date, "positive": 60 + (i % 20), "neutral": 25, "negative": 15})
    return list(reversed(trends))


@router.get("/resolution")
def get_resolution_metrics(
    current_user=Depends(require_roles(["hr", "admin"]))
):
    return {
        "total_resolved": 180,
        "total_tickets": 234,
        "resolution_rate": 0.77,
        "by_priority": {"critical": 0.95, "high": 0.88, "medium": 0.75, "low": 0.60}
    }


class AttritionRiskResponse(BaseModel):
    user_id: str
    name: str
    risk_score: float
    risk_level: str


class AttritionSummaryResponse(BaseModel):
    risk_scores: List[AttritionRiskResponse]
    average_risk: float


@router.get("/attrition", response_model=AttritionSummaryResponse)
def get_attrition_risk(
    department_id: Optional[UUID] = None,
    current_user=Depends(require_roles(["admin"]))
):
    """
    Get attrition risk analysis for users.
    
    Returns risk scores, levels, and factors for each user,
    along with average risk for the department or organization.
    """
    from ...services.attrition import AttritionRiskService
    
    service = AttritionRiskService()
    result = service.get_department_risk_summary(department_id)
    
    return result
