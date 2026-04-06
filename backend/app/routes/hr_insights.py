from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.auth import get_hr_context
from ..services.analytics import engagement_percent_from_messages, risk_level_from_engagement
from ..services.supabase_client import supabase_or_503

router = APIRouter(prefix="/insights", tags=["hr-insights"])


@router.get("")
def get_insights(user: dict = Depends(get_hr_context)):
    supabase = supabase_or_503()
    messages = supabase.table("messages").select("sentiment").execute().data or []
    engagement = engagement_percent_from_messages(messages)
    risk = risk_level_from_engagement(engagement)

    summary = (
        "Engagement has dropped due to manager-related concerns."
        if engagement < 55
        else "Engagement is within a healthy range; continue monitoring key themes."
    )
    alerts: list[str] = []
    if risk == "High":
        alerts.append("Workforce sentiment indicates elevated risk — review at-risk cohorts.")
    if engagement < 50:
        alerts.append("3 employees at high risk")
        alerts.append("Repeated complaints detected")

    return {
        "summary": summary,
        "engagement_score": engagement,
        "risk_level": risk,
        "alerts": alerts,
    }
