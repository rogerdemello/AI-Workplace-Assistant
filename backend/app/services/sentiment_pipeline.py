"""Per-message sentiment logging + employee-level score aggregation."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Dict, Iterable, Optional
from uuid import UUID

from sqlalchemy import desc, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from ..config import settings
from ..core.time import utcnow_naive
from ..models.conversation import Conversation, Message, MessageSender
from ..models.employee_score import EmployeeScore
from ..models.message_signal import MessageSignal
from ..models.sentiment_log import SentimentLog
from .engagement_score import EngagementScore
from .signal_extractor import extract_signals
from .sentiment import SentimentService
from .sustained_risk_alerts import notify_sustained_negative_pattern_if_needed

logger = logging.getLogger(__name__)

_EMOTION_KEYWORDS = {
    "frustration": ("frustrated", "frustration", "annoyed", "ignored"),
    "stress": ("stressed", "overwhelmed", "burnout", "exhausted"),
    "anger": ("angry", "furious", "rage", "mad"),
    "sadness": ("sad", "hopeless", "down", "disappointed"),
    "anxiety": ("anxious", "worried", "nervous"),
}


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _sentiment_100_from_label(label: str) -> int:
    if label == "positive":
        return 75
    if label == "negative":
        return 25
    return 50


def _normalize_sentiment_score(raw: Optional[float], label: str) -> int:
    if raw is None:
        return _sentiment_100_from_label(label)
    # Existing sentiment service returns -1..1; normalize to 0..100.
    if -1.0 <= raw <= 1.0:
        return _clamp_score((raw + 1.0) * 50.0)
    return _clamp_score(raw)


def _detect_emotion(text: str, label: str) -> str:
    lowered = (text or "").lower()
    for emotion, words in _EMOTION_KEYWORDS.items():
        if any(w in lowered for w in words):
            return emotion
    if label == "negative":
        return "frustration"
    if label == "positive":
        return "satisfaction"
    return "neutral"


def _safe_avg(values: Iterable[int], default: int) -> float:
    vals = list(values)
    if not vals:
        return float(default)
    return float(sum(vals) / len(vals))


def _apply_smoothing_guardrail(raw_score: int, previous_score: Optional[int], max_step: int = 10) -> int:
    """
    Damp one-turn volatility so single extreme chats don't whipsaw HR dashboards.
    Keeps sentiment responsive while limiting abrupt jumps per recompute cycle.
    """
    if previous_score is None:
        return raw_score
    delta = raw_score - int(previous_score)
    if abs(delta) <= max_step:
        return raw_score
    return int(previous_score) + (max_step if delta > 0 else -max_step)


class SentimentPipelineService:
    """Real-time sentiment -> trend -> risk pipeline for HR analytics."""

    def __init__(self, db: Session):
        self.db = db
        self.sentiment_service = SentimentService(db)

    def process_message(
        self,
        *,
        employee_id: UUID,
        message_id: UUID,
        message_text: str,
        sentiment_label: Optional[str] = None,
        sentiment_score: Optional[float] = None,
        intelligence_snapshot: Optional[Dict[str, object]] = None,
        conversation_id: Optional[UUID] = None,
    ) -> Dict[str, object]:
        topic: str = "general"
        severity: str = "low"

        if intelligence_snapshot:
            score_100 = _clamp_score(int(intelligence_snapshot.get("score_0_100", 50)))
            sentiment = str(intelligence_snapshot.get("label", "neutral"))
            if sentiment not in ("positive", "neutral", "negative"):
                sentiment = "neutral"
            analysis_source = str(
                intelligence_snapshot.get("analysis_source") or "llm_intelligence"
            )
            emotion = str(intelligence_snapshot.get("emotion", "neutral"))[:50]
            signal = extract_signals(message_text, sentiment)
            if intelligence_snapshot.get("topic"):
                topic = str(intelligence_snapshot.get("topic"))[:80]
            else:
                topic = signal["topic"]
            severity = signal["severity"]
        else:
            sentiment = sentiment_label or ""
            score_raw = sentiment_score
            analysis_source = "provided"
            if not sentiment:
                analyzed = self.sentiment_service.analyze(message_text, conversation_id=conversation_id)
                sentiment = str(analyzed.get("sentiment", "neutral"))
                score_raw = analyzed.get("score")
                analysis_source = str(analyzed.get("source") or "lexicon")
            score_100 = _normalize_sentiment_score(score_raw, sentiment)
            emotion = _detect_emotion(message_text, sentiment)
            signal = extract_signals(message_text, sentiment)
            topic = signal["topic"]
            severity = signal["severity"]

        self._log_sentiment(
            employee_id=employee_id,
            message_id=message_id,
            score=score_100,
            label=sentiment,
            emotion=emotion,
            analysis_source=analysis_source,
            conversation_id=conversation_id,
        )
        self._log_signal(
            employee_id=employee_id,
            message_id=message_id,
            emotion=emotion if intelligence_snapshot else signal["emotion"],
            topic=topic,
            severity=severity,
        )
        score_row = self._safe_recompute_employee_score(employee_id)
        try:
            from ..intelligence.engagement_service import EmployeeIntelligenceService

            EmployeeIntelligenceService(self.db).evaluate_alert_signals(score_row)
        except Exception:
            logger.debug("Intelligence alert evaluation skipped", exc_info=True)

        # NEW: Real-time sentiment alerts
        try:
            from .sentiment_alerts import SentimentAlertService
            alert_service = SentimentAlertService(self.db)
            alert_service.process_message_sentiment(
                employee_id=employee_id,
                message_id=message_id,
                sentiment_score=score_100,
                sentiment_label=sentiment,
                emotion=emotion if intelligence_snapshot else signal["emotion"],
                conversation_id=conversation_id,
            )
        except Exception:
            logger.debug("Sentiment alert processing skipped", exc_info=True)

        # NEW: Conversation risk scoring
        try:
            from .conversation_risk_scorer import ConversationRiskScorer
            risk_scorer = ConversationRiskScorer(self.db)
            if conversation_id:
                risk_metrics = risk_scorer.score_conversation(conversation_id)
                if risk_metrics and risk_metrics.requires_hr_attention:
                    logger.info(
                        "High-risk conversation detected: %s (score: %s)",
                        conversation_id,
                        risk_metrics.risk_score,
                    )
        except Exception:
            logger.debug("Conversation risk scoring skipped", exc_info=True)

        return {
            "score": score_100,
            "label": sentiment,
            "emotion": emotion if intelligence_snapshot else signal["emotion"],
            "topic": topic,
            "severity": severity,
            "employee_score": {
                "sentiment_score": score_row.sentiment_score,
                "trend": score_row.trend_label,
                "delta": score_row.trend_delta,
                "risk_score": score_row.risk_score,
            },
        }

    def refresh_employee_aggregate(self, employee_id: UUID) -> EmployeeScore:
        """Public entry for dashboard/API replays without a new message."""
        return self._recompute_employee_score(employee_id)

    def _safe_recompute_employee_score(self, employee_id: UUID) -> EmployeeScore:
        """Recompute aggregates; on schema drift or DB errors return a neutral placeholder (chat keeps working)."""
        try:
            return self._recompute_employee_score(employee_id)
        except (ProgrammingError, OperationalError):
            self.db.rollback()
            logger.warning(
                "employee score recompute skipped (likely schema drift vs sentiment_logs/message_signals)",
                exc_info=True,
            )
            row = self.db.query(EmployeeScore).filter(EmployeeScore.employee_id == employee_id).first()
            if row:
                return row
            placeholder = EmployeeScore(
                employee_id=employee_id,
                sentiment_score=50,
                engagement_score=50,
                risk_score=30,
                mental_health_score=50,
                trend_delta=0,
                trend_label="stable",
            )
            try:
                self.db.add(placeholder)
                self.db.commit()
                self.db.refresh(placeholder)
                return placeholder
            except (ProgrammingError, OperationalError):
                self.db.rollback()
                logger.warning("could not persist fallback EmployeeScore row", exc_info=True)

            class _NeutralScore:
                def __init__(self, eid: UUID) -> None:
                    self.employee_id = eid
                    self.sentiment_score = 50
                    self.trend_label = "stable"
                    self.trend_delta = 0
                    self.risk_score = 30

            return _NeutralScore(employee_id)  # type: ignore[return-value]

    def _log_sentiment(
        self,
        *,
        employee_id: UUID,
        message_id: UUID,
        score: int,
        label: str,
        emotion: str,
        analysis_source: Optional[str] = None,
        conversation_id: Optional[UUID] = None,
    ) -> None:
        # One log per message. Reprocessing happens for good reasons — a
        # reconcile run, a replayed failure, a retried request — and without
        # this guard each one silently adds a second row and skews the
        # employee's score. A partial unique index backs it at the database
        # level; this check keeps the common case from raising.
        if message_id is not None:
            already = (
                self.db.query(SentimentLog.id)
                .filter(SentimentLog.message_id == message_id)
                .first()
            )
            if already:
                return

        row = SentimentLog(
            employee_id=employee_id,
            conversation_id=conversation_id,
            message_id=message_id,
            score=score,
            label=label,
            emotion=emotion,
            analysis_source=analysis_source,
        )
        try:
            self.db.add(row)
            self.db.commit()
        except (ProgrammingError, OperationalError):
            self.db.rollback()
            log_id = uuid.uuid4()
            created = utcnow_naive()
            try:
                self.db.execute(
                    text(
                        """
                        INSERT INTO sentiment_logs (
                            id, employee_id, message_id, score, label, emotion, created_at
                        )
                        VALUES (
                            :id, :employee_id, :message_id, :score, :label, :emotion, :created_at
                        )
                        """
                    ),
                    {
                        "id": log_id,
                        "employee_id": employee_id,
                        "message_id": message_id,
                        "score": score,
                        "label": label[:20],
                        "emotion": emotion[:50],
                        "created_at": created,
                    },
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.warning(
                    "sentiment_logs insert skipped after ORM + minimal fallback failed",
                    exc_info=True,
                )

    def _log_signal(
        self,
        *,
        employee_id: UUID,
        message_id: UUID,
        emotion: str,
        topic: str,
        severity: str,
    ) -> None:
        row = MessageSignal(
            employee_id=employee_id,
            message_id=message_id,
            emotion=emotion,
            topic=topic,
            severity=severity,
        )
        try:
            self.db.add(row)
            self.db.commit()
        except (ProgrammingError, OperationalError):
            self.db.rollback()
            logger.warning("message_signals insert skipped (schema drift or missing table)", exc_info=True)

    def _recompute_employee_score(self, employee_id: UUID) -> EmployeeScore:
        now = utcnow_naive()
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)
        prev_week_start = now - timedelta(days=14)

        rows_30 = (
            self.db.query(SentimentLog)
            .filter(SentimentLog.employee_id == employee_id, SentimentLog.created_at >= month_start)
            .all()
        )
        rows_7 = [r for r in rows_30 if r.created_at >= week_start]
        rows_prev_7 = [r for r in rows_30 if prev_week_start <= r.created_at < week_start]

        avg7 = _safe_avg((r.score for r in rows_7), default=50)
        avg30 = _safe_avg((r.score for r in rows_30), default=50)
        base_blend = (0.7 * avg7) + (0.3 * avg30)
        rolling_n = max(2, min(30, int(settings.SENTIMENT_ROLLING_TURNS)))
        blend_w = float(settings.SENTIMENT_ROLLING_BLEND_WEIGHT)
        roll_rows = (
            self.db.query(SentimentLog.score)
            .filter(SentimentLog.employee_id == employee_id)
            .order_by(desc(SentimentLog.created_at))
            .limit(rolling_n)
            .all()
        )
        if blend_w > 0 and len(roll_rows) >= 2:
            rolling_avg = _safe_avg((r[0] for r in roll_rows), default=float(base_blend))
            combined = (1.0 - blend_w) * base_blend + blend_w * rolling_avg
            raw_weighted_sentiment = _clamp_score(combined)
        else:
            raw_weighted_sentiment = _clamp_score(base_blend)

        row = self.db.query(EmployeeScore).filter(EmployeeScore.employee_id == employee_id).first()
        previous_sentiment_score = int(row.sentiment_score) if row and row.sentiment_score is not None else None
        weighted_sentiment = _clamp_score(
            _apply_smoothing_guardrail(raw_weighted_sentiment, previous_sentiment_score, max_step=10)
        )

        prev_avg = _safe_avg((r.score for r in rows_prev_7), default=weighted_sentiment)
        delta = int(round(weighted_sentiment - prev_avg))
        if delta >= 5:
            trend = "up"
        elif delta <= -5:
            trend = "down"
        else:
            trend = "stable"

        sustained_window_days = max(1, int(settings.SUSTAINED_NEGATIVE_WINDOW_DAYS))
        sustained_start = now - timedelta(days=sustained_window_days)
        negative_turns_sustained = sum(
            1 for r in rows_30 if r.created_at >= sustained_start and r.label == "negative"
        )
        min_neg = max(1, int(settings.SUSTAINED_NEGATIVE_MIN_MESSAGES))
        repeated_negative = negative_turns_sustained >= min_neg
        complaint_count_7 = (
            self.db.query(MessageSignal.id)
            .filter(
                MessageSignal.employee_id == employee_id,
                MessageSignal.created_at >= week_start,
                MessageSignal.topic.in_(["manager_issue", "workload", "salary", "recognition"]),
            )
            .count()
        )
        last_message = (
            self.db.query(Message.created_at)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .filter(Conversation.user_id == employee_id, Message.sender == MessageSender.user)
            .order_by(Message.created_at.desc())
            .first()
        )
        inactive_days = (now - last_message[0]).days if last_message and last_message[0] else 99

        inactivity_score = _clamp_score((inactive_days / 10.0) * 100.0)
        complaint_frequency = _clamp_score((complaint_count_7 / 5.0) * 100.0)
        trend_drop = _clamp_score(max(0, -delta) * 4.0)
        negativity_component = (100 - weighted_sentiment) * 0.4
        inactivity_component = inactivity_score * 0.2
        complaint_component = complaint_frequency * 0.2
        trend_component = trend_drop * 0.2
        risk = _clamp_score(
            negativity_component
            + inactivity_component
            + complaint_component
            + trend_component
        )
        sustained_bump = 8 if repeated_negative else 0
        if sustained_bump:
            risk = _clamp_score(risk + sustained_bump)

        # Keep the reasoning, not just the verdict. `contributions` are points
        # of the final score so they can be read as "inactivity is 20 of this
        # 46" — the distinction between someone on holiday and someone in
        # trouble. `evidence` is the raw input each one came from, and
        # `messages_30d` is how much data the whole thing rests on: a score
        # built on two messages deserves far less weight than one built on 200.
        risk_factors = {
            "contributions": {
                "negativity": round(negativity_component, 1),
                "inactivity": round(inactivity_component, 1),
                "complaints": round(complaint_component, 1),
                "trend_drop": round(trend_component, 1),
                "sustained_negative_bump": sustained_bump,
            },
            "evidence": {
                "sentiment_score": int(weighted_sentiment),
                "days_since_last_message": int(inactive_days),
                "complaint_signals_7d": int(complaint_count_7),
                "negative_turns_in_window": int(negative_turns_sustained),
                "trend_delta": int(delta),
            },
            "confidence": {
                "messages_30d": len(rows_30),
                "messages_7d": len(rows_7),
            },
            "computed_at": now.isoformat(),
        }

        try:
            engagement = _clamp_score(EngagementScore(self.db).calculate_user_engagement(employee_id, days=30)["engagement_score"])
        except Exception:
            engagement = 50
        mental_health = _clamp_score((weighted_sentiment * 0.7) + ((100 - risk) * 0.3))

        if not row:
            row = EmployeeScore(employee_id=employee_id)
            self.db.add(row)

        row.sentiment_score = weighted_sentiment
        row.engagement_score = engagement
        row.risk_score = risk
        row.mental_health_score = mental_health
        row.trend_delta = delta
        row.trend_label = trend
        row.risk_factors = risk_factors
        row.last_updated = now
        self.db.commit()
        self.db.refresh(row)

        if repeated_negative:
            try:
                notify_sustained_negative_pattern_if_needed(
                    self.db,
                    employee_id=employee_id,
                    negative_count_in_window=negative_turns_sustained,
                    window_days=sustained_window_days,
                )
            except Exception:
                logger.warning("Sustained risk HR notification skipped", exc_info=True)

        return row
