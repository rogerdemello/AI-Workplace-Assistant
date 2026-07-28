from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Any, Dict, List, Optional


class KPIResponse(BaseModel):
    engagement_score: float
    resolution_rate: float
    avg_response_time: float
    active_users: int
    total_tickets: int
    open_tickets: int
    enps: float = 0.0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "engagement_score": 72.5,
                "resolution_rate": 0.81,
                "avg_response_time": 5.4,
                "active_users": 128,
                "total_tickets": 420,
                "open_tickets": 79,
                "enps": 34.0,
            }
        }
    )


class SentimentTrendResponse(BaseModel):
    date: str
    positive: float
    neutral: float
    negative: float


class EmotionTrendResponse(BaseModel):
    date: str
    emotions: Dict[str, float]


class SentimentSourceDriftResponse(BaseModel):
    """Counts of sentiment_logs by analysis_source over a rolling window (HR classifier drift)."""

    window_days: int
    total: int
    by_source: Dict[str, int]
    pct_by_source: Dict[str, float]


class SentimentSourceTrendResponse(BaseModel):
    date: str
    sources: Dict[str, float]


class EmployeeInsightResponse(BaseModel):
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
    #: Full breakdown behind risk_score — contributions in points, the raw
    #: evidence each came from, and how many messages it rests on.
    risk_factors: Optional[Dict[str, Any]] = None
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
    metrics: KPIResponse
    sentiment: List[SentimentTrendResponse]
    employees: List[EmployeeInsightResponse]
    weekly_quality: WeeklyQualityResponse
    ai_summary: str
    manager_pattern: Optional[dict] = None
    sentiment_stale_days: int = 7
    sustained_risk_window_days: int = 7
    sustained_risk_min_negative_turns: int = 3
    sentiment_source_drift: SentimentSourceDriftResponse
    last_chat_sentiment_at: Optional[datetime] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metrics": {
                    "engagement_score": 72.5,
                    "resolution_rate": 0.81,
                    "avg_response_time": 5.4,
                    "active_users": 128,
                    "total_tickets": 420,
                    "open_tickets": 79,
                    "enps": 34.0,
                },
                "sentiment": [
                    {"date": "2026-04-26", "positive": 58.0, "neutral": 30.0, "negative": 12.0},
                    {"date": "2026-04-27", "positive": 55.0, "neutral": 33.0, "negative": 12.0},
                ],
                "employees": [
                    {
                        "id": "ad5188b4-6e5c-4e4e-8650-f6179ea4f1ee",
                        "employee_id": "EMP1022",
                        "name": "Alex Lee",
                        "sentiment_score": 68,
                        "risk_score": 41,
                        "last_active": "2 hours ago",
                        "department": "Engineering",
                        "risk_label": "Medium",
                    }
                ],
                "weekly_quality": {
                    "window_days": 7,
                    "feedback_responses": 34,
                    "avg_csat": 4.35,
                    "helpful_rate": 82.4,
                    "detractor_rate": 8.8,
                    "avg_first_response_seconds": 21.7,
                    "conversations_measured": 103,
                    "quality_label": "Good",
                },
                "ai_summary": "3 open tickets about manager issues - recommend HR check-in.",
                "manager_pattern": {"manager_id": "f968...", "manager": "Priya Shah", "count": 4},
            }
        }
    )


class AttritionRiskResponse(BaseModel):
    user_id: str
    name: str
    risk_score: float
    risk_level: str


class AttritionSummaryResponse(BaseModel):
    risk_scores: List[AttritionRiskResponse]
    average_risk: float


class AttritionFactorResponse(BaseModel):
    name: str
    description: str
    direction: str
    raw_value: float
    risk_value: float
    weight: float
    contribution: float
    contribution_pct: float


class AttritionUserRiskResponse(BaseModel):
    user_id: str
    name: str
    risk_score: float
    calibrated_risk_score: float
    risk_level: str
    confidence: float
    calibration_band: str
    factors: List[AttritionFactorResponse]
    history: List[dict]


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


class ManagerEffectivenessResponse(BaseModel):
    manager_id: str
    manager_name: str
    team_size: int
    avg_sentiment_score: float
    avg_risk_score: float
    open_complaints: int
    engagement_ratio: float
    effectiveness_score: float
    effectiveness_label: str


class ManagerDashboardBundleResponse(BaseModel):
    manager_id: str
    team_size: int
    avg_team_sentiment: float
    avg_team_risk: float
    high_risk_count: int
    open_complaints: int
    employees: List[EmployeeInsightResponse]

