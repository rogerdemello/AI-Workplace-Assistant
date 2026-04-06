from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.auth import get_hr_context
from ..services.analytics import (
    count_open_tickets,
    engagement_percent_from_messages,
    risk_level_from_engagement,
)
from ..services.hr_sentiment_metrics import sentiment_trend_rows
from ..services.supabase_client import supabase_or_503

router = APIRouter(tags=["hr-dashboard"])


@router.get("/dashboard")
def get_dashboard(user: dict = Depends(get_hr_context)):
    supabase = supabase_or_503()
    messages = supabase.table("messages").select("sentiment").execute().data or []
    tickets = supabase.table("tickets").select("id,status").execute().data or []

    engagement_score = engagement_percent_from_messages(messages)
    risk_level = risk_level_from_engagement(engagement_score)
    open_tickets = count_open_tickets(tickets)

    return {
        "engagement_score": engagement_score,
        "risk_level": risk_level,
        "open_tickets": open_tickets,
    }


@router.get("/sentiment-trend")
def sentiment_trend(user: dict = Depends(get_hr_context)):
    supabase = supabase_or_503()
    messages = (
        supabase.table("messages").select("sentiment,created_at").execute().data or []
    )
    return sentiment_trend_rows(messages)
