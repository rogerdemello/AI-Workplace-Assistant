"""API endpoints for sentiment alerts and conversation risk scoring."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...database import get_db
from ...models.user import User
from ...auth import get_current_user, require_roles
from ...services.sentiment_alerts import SentimentAlertService, get_sentiment_alert_service
from ...services.conversation_risk_scorer import ConversationRiskScorer, get_conversation_risk_scorer

router = APIRouter(prefix="/sentiment-alerts", tags=["sentiment-alerts"])


@router.get("/active")
def get_active_sentiment_alerts(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Get all active sentiment alerts within time window."""
    service = get_sentiment_alert_service(db)
    return {
        "alerts": service.get_active_alerts(hours=hours),
        "count": len(service.get_active_alerts(hours=hours)),
    }


@router.get("/employee/{employee_id}")
def get_employee_sentiment_alerts(
    employee_id: UUID,
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Get sentiment alerts for a specific employee."""
    service = get_sentiment_alert_service(db)
    all_alerts = service.get_active_alerts(hours=hours)
    employee_alerts = [a for a in all_alerts if a["employee_id"] == str(employee_id)]
    return {
        "employee_id": str(employee_id),
        "alerts": employee_alerts,
        "count": len(employee_alerts),
    }


@router.post("/dismiss/{alert_id}")
def dismiss_sentiment_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Dismiss a sentiment alert."""
    service = get_sentiment_alert_service(db)
    success = service.dismiss_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert dismissed"}


@router.get("/conversation-risk/{conversation_id}")
def get_conversation_risk(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Get risk metrics for a specific conversation."""
    scorer = get_conversation_risk_scorer(db)
    metrics = scorer.score_conversation(conversation_id)
    
    if not metrics:
        raise HTTPException(status_code=404, detail="Conversation not found or no sentiment data")
    
    return {
        "conversation_id": str(metrics.conversation_id),
        "employee_id": str(metrics.employee_id),
        "total_messages": metrics.total_messages,
        "sentiment_breakdown": {
            "negative": metrics.negative_count,
            "neutral": metrics.neutral_count,
            "positive": metrics.positive_count,
        },
        "average_sentiment": metrics.average_sentiment,
        "sentiment_trend": metrics.sentiment_trend,
        "risk_score": metrics.risk_score,
        "alert_level": metrics.alert_level,
        "dominant_emotion": metrics.dominant_emotion,
        "emotions_detected": metrics.emotions_detected,
        "requires_hr_attention": metrics.requires_hr_attention,
    }


@router.get("/employee-risk/{employee_id}")
def get_employee_risk_summary(
    employee_id: UUID,
    days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Get aggregated risk summary for an employee."""
    scorer = get_conversation_risk_scorer(db)
    summary = scorer.get_employee_risk_summary(employee_id, days=days)
    
    # Also get conversation details
    conversations = scorer.score_employee_conversations(employee_id, days=days)
    
    return {
        **summary,
        "conversations": [
            {
                "conversation_id": str(c.conversation_id),
                "risk_score": c.risk_score,
                "alert_level": c.alert_level,
                "total_messages": c.total_messages,
                "sentiment_trend": c.sentiment_trend,
                "dominant_emotion": c.dominant_emotion,
                "requires_hr_attention": c.requires_hr_attention,
            }
            for c in conversations
        ],
    }


@router.get("/high-risk-conversations")
def get_high_risk_conversations(
    min_risk: int = Query(default=70, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _hr=Depends(require_roles(["hr", "admin"])),
):
    """Get high-risk conversations across all employees."""
    scorer = get_conversation_risk_scorer(db)
    conversations = scorer.get_high_risk_conversations(min_risk=min_risk, limit=limit)
    
    return {
        "conversations": [
            {
                "conversation_id": str(c.conversation_id),
                "employee_id": str(c.employee_id),
                "risk_score": c.risk_score,
                "alert_level": c.alert_level,
                "total_messages": c.total_messages,
                "negative_count": c.negative_count,
                "sentiment_trend": c.sentiment_trend,
                "dominant_emotion": c.dominant_emotion,
                "requires_hr_attention": c.requires_hr_attention,
            }
            for c in conversations
        ],
        "count": len(conversations),
    }
