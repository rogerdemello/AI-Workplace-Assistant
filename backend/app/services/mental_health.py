"""
Mental Health Scoring Service - Unified mental health score combining existing services.

Combines:
- Sentiment analysis (weight: 0.5)
- Engagement score (weight: 0.3)
- Risk assessment (weight: 0.2, inverted)

Formula: (sentiment × 0.5) + (engagement × 0.3) + ((100 - risk) × 0.2)

Score ranges:
- 80-100: healthy
- 60-80: stable
- 40-60: at_risk
- 20-40: struggling
- 0-20: critical
"""

import logging
from datetime import date
from typing import Dict
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..models.analytics import MentalHealthScore
from ..models.hr_alert import HrAlert
from ..models.automation_action import AutomationAction
from ..models.risk_snapshot import RiskSnapshot
from ..core.time import utcnow_naive
from .engagement_score import EngagementScore
from .sentiment import SentimentService

logger = logging.getLogger(__name__)


def _get_sentiment_score(db: Session, user_id: UUID, days: int = 30) -> int:
    """Get sentiment score converted to 0-100 scale."""
    sentiment_service = SentimentService(db)
    trend = sentiment_service.get_trend(user_id=user_id, days=days)
    
    # average_sentiment ranges from -1 to 1
    average = trend.get("average_sentiment", 0.0)
    
    # Convert -1 to 1 → 0 to 100
    # -1 → 0, 0 → 50, 1 → 100
    score = (average + 1) * 50
    return max(0, min(100, int(score)))


def _get_engagement_score(db: Session, user_id: UUID, days: int = 30) -> int:
    """Get engagement score from existing service."""
    engagement_service = EngagementScore(db)
    result = engagement_service.calculate_user_engagement(user_id, days=days)
    return max(0, min(100, round(result["engagement_score"])))


def _get_risk_score(db: Session, user_id: UUID) -> int:
    snapshot = (
        db.query(RiskSnapshot)
        .filter(RiskSnapshot.user_id == user_id)
        .order_by(desc(RiskSnapshot.created_at))
        .first()
    )
    
    if not snapshot:
        return 50
    
    ar = snapshot.attrition_risk
    if ar is None:
        return 50
    risk_val = float(ar)
    return max(0, min(100, int(risk_val)))


def _get_status(mental_health_score: int) -> str:
    """Determine status based on mental health score."""
    if mental_health_score >= 80:
        return "healthy"
    elif mental_health_score >= 60:
        return "stable"
    elif mental_health_score >= 40:
        return "at_risk"
    elif mental_health_score >= 20:
        return "struggling"
    else:
        return "critical"


def calculate_mental_health(db: Session, user_id: UUID, days: int = 30) -> Dict:
    """
    Calculate unified mental health score combining sentiment, engagement, and risk.
    
    Args:
        db: Database session
        user_id: User UUID to calculate score for
        days: Number of days to look back for sentiment/engagement (default: 30)
    
    Returns:
        Dict with:
        - mental_health: int (0-100)
        - sentiment: int (0-100)
        - engagement: int (0-100)
        - risk: int (0-100)
        - status: str ("healthy" | "stable" | "at_risk" | "struggling" | "critical")
    """
    # Fetch individual scores
    sentiment = _get_sentiment_score(db, user_id, days)
    engagement = _get_engagement_score(db, user_id, days)
    risk = _get_risk_score(db, user_id)
    
    # Calculate unified mental health score
    # Formula: (sentiment × 0.5) + (engagement × 0.3) + ((100-risk) × 0.2)
    mental_health = (sentiment * 0.5) + (engagement * 0.3) + ((100 - risk) * 0.2)
    mental_health = max(0, min(100, round(mental_health)))
    
    # Determine status
    status = _get_status(mental_health)
    
    return {
        "mental_health": mental_health,
        "sentiment": sentiment,
        "engagement": engagement,
        "risk": risk,
        "status": status
    }


def create_risk_alert(
    db: Session,
    user_id: UUID,
    alert_type: str,
    severity: str,
    title: str | None = None,
    body: str | None = None,
) -> HrAlert | None:
    """
    Create an HR alert for mental health risk escalation.
    
    Args:
        db: Database session
        user_id: User UUID
        alert_type: Type of alert (e.g., "mental_health_at_risk", "mental_health_critical")
        severity: Severity level ("medium" | "high" | "critical")
        title: Optional title override
        body: Optional body override
    
    Returns:
        Created HrAlert instance
    """
    # Idempotency: prevent duplicate alerts for same user/alert_type within 1 hour
    hour_key = utcnow_naive().strftime("%Y%m%d%H")
    idempotency_key = f"mental-health:{alert_type}:{user_id}:{hour_key}"
    
    existing = (
        db.query(AutomationAction)
        .filter(
            AutomationAction.rule_name == "mental_health_alert",
            AutomationAction.idempotency_key == idempotency_key,
        )
        .first()
    )
    if existing:
        return None
    
    # Determine title/body if not provided
    if title is None:
        if alert_type == "mental_health_critical":
            title = "CRITICAL: Immediate mental health concern"
        else:
            title = "Mental health risk detected"
    
    if body is None:
        body = f"User {user_id} triggered {alert_type} alert. Immediate HR follow-up recommended."
    
    alert = HrAlert(
        title=title,
        body=body,
        severity=severity,
        alert_type=alert_type,
        source="mental_health_monitor",
    )
    db.add(alert)
    db.flush()

    # Best-effort Teams fan-out — no-op when Teams isn't configured.
    try:
        from .teams_service import notify_hr_alert as _teams_notify
        _teams_notify(title=title, body=body, severity=severity)
    except Exception:
        pass
    
    # Record automation action for idempotency
    action = AutomationAction(
        rule_name="mental_health_alert",
        user_id=user_id,
        target_type="hr",
        action_type="hr_alert",
        status="sent",
        executed_at=utcnow_naive(),
        idempotency_key=idempotency_key,
        trigger_context={"alert_type": alert_type, "severity": severity},
    )
    db.add(action)
    db.commit()
    
    return alert


def check_and_alert_mental_health(
    db: Session,
    user_id: UUID,
    days: int = 30,
) -> Dict:
    """
    Calculate mental health score and create alert if below threshold.
    
    Args:
        db: Database session
        user_id: User UUID
        days: Number of days for score calculation
    
    Returns:
        Dict with score info and alert action taken
    """
    result = calculate_mental_health(db, user_id, days)
    mental_health = result["mental_health"]
    status = result["status"]

    try:
        existing = (
            db.query(MentalHealthScore)
            .filter(
                MentalHealthScore.user_id == user_id,
                MentalHealthScore.created_at_date == date.today(),
            )
            .first()
        )
        if existing:
            existing.score = mental_health
            existing.factors = {
                "sentiment": result["sentiment"],
                "engagement": result["engagement"],
                "risk": result["risk"],
                "status": status,
            }
            existing.trend = status
        else:
            db.add(
                MentalHealthScore(
                    user_id=user_id,
                    score=mental_health,
                    factors={
                        "sentiment": result["sentiment"],
                        "engagement": result["engagement"],
                        "risk": result["risk"],
                        "status": status,
                    },
                    trend=status,
                    created_at_date=date.today(),
                )
            )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Mental health score persistence skipped: %s", exc)

    alert_created = False
    alert = None
    
    # Thresholds:
    # - at_risk (<40) -> HR notify (medium/high)
    # - critical (<20) -> immediate escalation (critical)
    if mental_health < 20:
        # Critical: immediate escalation
        alert = create_risk_alert(
            db=db,
            user_id=user_id,
            alert_type="mental_health_critical",
            severity="critical",
        )
        alert_created = True
    elif mental_health < 40:
        # At risk: HR notification
        alert = create_risk_alert(
            db=db,
            user_id=user_id,
            alert_type="mental_health_at_risk",
            severity="high",
        )
        alert_created = True
    
    return {
        "mental_health": mental_health,
        "status": status,
        "alert_created": alert_created,
        "alert_id": str(alert.id) if alert else None,
    }


__all__ = ["calculate_mental_health", "create_risk_alert", "check_and_alert_mental_health"]