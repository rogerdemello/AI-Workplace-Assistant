from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..config import settings
from ..models.activity_event import ActivityEvent
from ..models.employee_score import EmployeeScore
from ..core.time import utcnow_naive
from .realtime_bus import realtime_bus

logger = logging.getLogger(__name__)

#: Prefix on Message.intent identifying a proactively-delivered nudge.
NUDGE_INTENT_PREFIX = "nudge:"
from ..models.automation_action import AutomationAction
from ..models.automation_rule import AutomationRule
from ..models.conversation import Conversation, Message, MessageSender
from ..models.hr_alert import HrAlert
from ..models.reminder_schedule import ReminderSchedule
from ..models.risk_snapshot import RiskSnapshot
from ..models.ticket import Ticket, TicketStatus
from ..models.user import User, UserRole, UserStatus
from ..models.wellbeing_signal import WellbeingSignal
from .engagement_score import EngagementScore
from .sentiment import SentimentService


class MarkProactiveService:
    DEFAULT_SUPPRESSION_POLICY: Dict[str, Any] = {
        "enabled": True,
        "global_daily_max": 8,
        "break_nudge_cooldown_minutes": 60,
        "break_nudge_daily_max": 2,
        "scheduled_reminder_cooldown_minutes": 20,
        "scheduled_reminder_daily_max": 10,
        "daily_checkin_followup_cooldown_minutes": 240,
        "daily_checkin_followup_daily_max": 1,
    }

    STRESS_KEYWORDS = [
        "stressed",
        "overwhelmed",
        "burnout",
        "exhausted",
        "anxious",
        "panic",
        "frustrated",
        "depressed",
    ]

    WORKLOAD_KEYWORDS = [
        "deadline",
        "workload",
        "too much",
        "pressure",
        "backlog",
        "late nights",
    ]

    ACTIVE_EVENT_TYPES = {
        "chat_message",
        "typing",
        "work_session",
        "app_focus",
        "task_update",
    }

    BREAK_EVENT_TYPES = {"break_taken", "away", "idle"}

    def __init__(self, db: Session):
        self.db = db
        self.sentiment = SentimentService(db=db)

    def get_suppression_policy(self) -> Dict[str, Any]:
        row = (
            self.db.query(AutomationRule)
            .filter(
                AutomationRule.event_type == "proactive_policy_config",
                AutomationRule.name == "default_suppression_policy",
            )
            .first()
        )
        if not row:
            return dict(self.DEFAULT_SUPPRESSION_POLICY)
        payload = row.actions or {}
        merged = dict(self.DEFAULT_SUPPRESSION_POLICY)
        merged.update(payload)
        return merged

    def update_suppression_policy(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        current = self.get_suppression_policy()
        current.update({k: v for k, v in updates.items() if v is not None})
        row = (
            self.db.query(AutomationRule)
            .filter(
                AutomationRule.event_type == "proactive_policy_config",
                AutomationRule.name == "default_suppression_policy",
            )
            .first()
        )
        if not row:
            row = AutomationRule(
                name="default_suppression_policy",
                event_type="proactive_policy_config",
                enabled=True,
                conditions={},
                actions=current,
                created_by=None,
            )
            self.db.add(row)
        else:
            row.actions = current
        self.db.commit()
        return current

    def _is_suppressed(
        self,
        *,
        user_id: UUID,
        action_type: str,
        rule_name: str,
        now: datetime,
    ) -> bool:
        policy = self.get_suppression_policy()
        if not bool(policy.get("enabled", True)):
            return False

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        global_max = int(policy.get("global_daily_max", 8))
        global_count = (
            self.db.query(func.count(AutomationAction.id))
            .filter(
                AutomationAction.user_id == user_id,
                AutomationAction.created_at >= today_start,
                AutomationAction.action_type.in_(["nudge", "reminder", "followup_offer"]),
            )
            .scalar()
            or 0
        )
        if global_count >= global_max:
            return True

        key_prefix = (
            "break_nudge"
            if rule_name == "break_reminder"
            else "scheduled_reminder"
            if rule_name == "scheduled_reminder"
            else "daily_checkin_followup"
            if rule_name == "daily_checkin_followup"
            else ""
        )
        if not key_prefix:
            return False

        daily_max = int(policy.get(f"{key_prefix}_daily_max", 999))
        event_count = (
            self.db.query(func.count(AutomationAction.id))
            .filter(
                AutomationAction.user_id == user_id,
                AutomationAction.rule_name == rule_name,
                AutomationAction.created_at >= today_start,
            )
            .scalar()
            or 0
        )
        if event_count >= daily_max:
            return True

        cooldown_minutes = int(policy.get(f"{key_prefix}_cooldown_minutes", 0))
        if cooldown_minutes <= 0:
            return False
        recent = (
            self.db.query(AutomationAction)
            .filter(
                AutomationAction.user_id == user_id,
                AutomationAction.rule_name == rule_name,
                AutomationAction.created_at >= now - timedelta(minutes=cooldown_minutes),
            )
            .first()
        )
        return recent is not None

    def _recent_activity_count(self, user_id: UUID, now: datetime) -> int:
        window_start = now - timedelta(hours=2, minutes=30)
        return (
            self.db.query(func.count(ActivityEvent.id))
            .filter(
                ActivityEvent.user_id == user_id,
                ActivityEvent.event_at >= window_start,
                ActivityEvent.event_type.in_(list(self.ACTIVE_EVENT_TYPES)),
            )
            .scalar()
            or 0
        )

    def decide_nudge_eligibility(
        self,
        *,
        user_id: UUID,
        nudge_type: str,
        message: str,
        now: Optional[datetime] = None,
    ) -> Tuple[bool, str]:
        """Optional LLM gate: would this nudge actually help the user right now?

        Returns ``(eligible, reason)``. When ``NUDGE_AI_GATING_ENABLED`` is off
        this is a no-op that always allows. Any LLM/parse error fails OPEN so a
        legitimate nudge is never silently dropped by an outage.
        """
        if not bool(getattr(settings, "NUDGE_AI_GATING_ENABLED", False)):
            return True, "ai_gating_disabled"

        now = now or utcnow_naive()
        score_row = (
            self.db.query(EmployeeScore)
            .filter(EmployeeScore.employee_id == user_id)
            .first()
        )
        sentiment = int(score_row.sentiment_score) if score_row else 50
        activity = self._recent_activity_count(user_id, now)
        last_nudge = (
            self.db.query(AutomationAction.created_at)
            .filter(
                AutomationAction.user_id == user_id,
                AutomationAction.action_type.in_(["nudge", "reminder", "followup_offer"]),
            )
            .order_by(AutomationAction.created_at.desc())
            .limit(1)
            .scalar()
        )
        mins_since_last = (
            int((now - last_nudge).total_seconds() // 60) if last_nudge else None
        )

        prompt = (
            "You decide whether a workplace wellbeing bot should send a nudge "
            "right now. Be conservative — only say yes if it genuinely helps and "
            "won't feel intrusive.\n\n"
            f"Nudge type: {nudge_type}\n"
            f"Draft message: {message}\n"
            f"User sentiment score (0=low, 100=great): {sentiment}\n"
            f"Active events in last 2.5h: {activity}\n"
            f"Minutes since last nudge: {mins_since_last if mins_since_last is not None else 'never'}\n\n"
            'Reply with strict JSON: {"send": true|false, "reason": "<short reason>"}'
        )

        try:
            from ..ai_client import get_ai_client

            client = get_ai_client()
            resp = client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a concise, caring decision engine. Output only JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=120,
            )
            content = resp["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            send = bool(parsed.get("send", True))
            reason = str(parsed.get("reason", "")).strip()[:200] or "ai_decision"
            return send, reason
        except Exception as exc:  # fail open — never block a nudge on an outage
            logger.warning("Nudge AI gate failed open: %s", exc)
            return True, "ai_gate_error_failopen"

    def notify_user(
        self,
        user_id: UUID,
        message: str,
        nudge_type: str = "hr_update",
        action_url: Optional[str] = None,
    ) -> None:
        """Send an employee a message from Mark: durable in chat, live over SSE.

        Public entry point for callers outside the proactive scheduler (e.g. HR
        actioning a request) that need to close the loop with an employee.
        Adds to the session; the caller owns the commit.
        """
        self._publish_user_nudge(user_id, message, nudge_type, action_url=action_url)

    def _persist_nudge_message(self, user_id: UUID, message: str, nudge_type: str) -> None:
        """Write the nudge into the user's chat history so it survives being offline.

        SSE only reaches a chat that is currently open. The employees these
        nudges target most — the quiet ones — are precisely the people without
        the app open, and a one-time reminder is closed out after firing. Without
        a durable copy the check-in is published to nobody and never retried.
        The message is added to the session; callers own the commit.
        """
        conversation = (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.started_at.desc())
            .first()
        )
        if conversation is None:
            conversation = Conversation(user_id=user_id)
            self.db.add(conversation)
            self.db.flush()

        self.db.add(
            Message(
                conversation_id=conversation.id,
                sender=MessageSender.bot,
                message_text=message,
                # NUDGE_INTENT_PREFIX marks these as proactively-sent so the chat
                # client can pull the ones it missed while the user was away.
                intent=f"{NUDGE_INTENT_PREFIX}{nudge_type}",
            )
        )

    def _publish_user_nudge(
        self,
        user_id: UUID,
        message: str,
        nudge_type: str,
        action_url: Optional[str] = None,
    ) -> None:
        """Deliver a nudge: persisted to chat history, plus live SSE if listening.

        ``action_url`` (optional) lets the client render a CTA button, e.g. a
        deep link to a lifecycle survey.
        """
        try:
            self._persist_nudge_message(user_id, message, nudge_type)
        except Exception:
            logger.warning("Failed to persist nudge for user %s", user_id, exc_info=True)

        payload: Dict[str, Any] = {
            "user_id": str(user_id),
            "message": message,
            "nudge_type": nudge_type,
        }
        if action_url:
            payload["action_url"] = action_url
        try:
            asyncio.run(realtime_bus.publish("user_nudge", payload))
        except Exception:
            pass

    @staticmethod
    def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return max(minimum, min(maximum, value))

    @staticmethod
    def _label_from_score(score: float) -> str:
        if score <= -0.2:
            return "negative"
        if score >= 0.2:
            return "positive"
        return "neutral"

    def _extract_keywords(self, text: str, candidates: List[str]) -> List[str]:
        lowered = (text or "").lower()
        return [kw for kw in candidates if kw in lowered]

    def _compute_stress_and_burnout(
        self,
        sentiment_score: float,
        text: str,
    ) -> tuple[float, float, List[str]]:
        stress_words = self._extract_keywords(text, self.STRESS_KEYWORDS)
        workload_words = self._extract_keywords(text, self.WORKLOAD_KEYWORDS)

        base_stress = self._clamp(-sentiment_score)
        stress_bonus = min(0.35, 0.1 * len(stress_words))
        stress_indicator = self._clamp(base_stress + stress_bonus)

        burnout_bonus = min(0.3, 0.1 * len(workload_words))
        burnout_indicator = self._clamp(stress_indicator * 0.7 + burnout_bonus)

        detected = stress_words + [w for w in workload_words if w not in stress_words]
        return stress_indicator, burnout_indicator, detected

    def _create_hr_alert_if_needed(
        self,
        user_id: UUID,
        triage_level: str,
        sentiment_score: float,
        text: str,
        signal_id: UUID,
    ) -> None:
        if triage_level != "high":
            return

        idempotency_key = f"negative-sentiment:{user_id}:{utcnow_naive().strftime('%Y%m%d%H')}"
        existing = (
            self.db.query(AutomationAction)
            .filter(
                AutomationAction.rule_name == "negative_sentiment_alert",
                AutomationAction.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            return

        alert = HrAlert(
            title="Potential wellbeing risk detected",
            body=(
                f"User {user_id} triggered a high-risk sentiment signal. "
                f"Score={sentiment_score:.2f}, Signal={signal_id}, Preview={(text or '')[:160]}"
            ),
            severity="high",
            alert_type="negative_sentiment",
            source="mark_wellbeing",
        )
        self.db.add(alert)

        action = AutomationAction(
            rule_name="negative_sentiment_alert",
            user_id=user_id,
            target_type="hr",
            action_type="hr_alert",
            status="sent",
            executed_at=utcnow_naive(),
            idempotency_key=idempotency_key,
            trigger_context={"signal_id": str(signal_id), "sentiment_score": sentiment_score},
        )
        self.db.add(action)

    def _upsert_daily_risk_snapshot(self, user_id: UUID) -> RiskSnapshot:
        today = date.today()
        now = utcnow_naive()

        signals = (
            self.db.query(WellbeingSignal)
            .filter(
                WellbeingSignal.user_id == user_id,
                WellbeingSignal.computed_at >= now - timedelta(days=14),
            )
            .all()
        )

        if signals:
            avg_sentiment = sum(float(s.sentiment_score or 0.0) for s in signals) / len(signals)
            avg_burnout = sum(float(s.burnout_indicator or 0.0) for s in signals) / len(signals)
        else:
            avg_sentiment = 0.0
            avg_burnout = 0.2

        mood_score = round(self._clamp((avg_sentiment + 1.0) / 2.0) * 100.0, 1)
        burnout_risk = round(self._clamp(avg_burnout), 3)

        last_user_message = (
            self.db.query(func.max(Message.created_at))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == user_id, Message.sender == MessageSender.user)
            .scalar()
        )
        if last_user_message:
            silence_days = max(0.0, (now - last_user_message).total_seconds() / 86400.0)
            silence_risk = self._clamp(silence_days / 7.0)
        else:
            silence_risk = 0.8

        engagement = EngagementScore(self.db).calculate_user_engagement(user_id=user_id, days=30)
        engagement_score = float(engagement.get("engagement_score", 50.0))

        open_tickets = (
            self.db.query(func.count(Ticket.id))
            .filter(
                Ticket.user_id == user_id,
                Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]),
            )
            .scalar()
            or 0
        )
        ticket_pressure = min(1.0, float(open_tickets) / 5.0)

        attrition_risk = self._clamp(
            (1.0 - engagement_score / 100.0) * 0.45
            + burnout_risk * 0.25
            + silence_risk * 0.2
            + ticket_pressure * 0.1
        )

        confidence = min(0.95, 0.55 + min(len(signals), 20) * 0.02)

        reasons: List[str] = []
        recommendations: List[str] = []
        if burnout_risk >= 0.65:
            reasons.append("High burnout indicators from recent conversations")
            recommendations.append("Manager check-in and workload review")
        if silence_risk >= 0.6:
            reasons.append("Low recent interaction indicates possible disengagement")
            recommendations.append("Send low-friction wellbeing nudge")
        if engagement_score < 45:
            reasons.append("Low engagement score over the last 30 days")
            recommendations.append("Plan HR follow-up with direct manager")
        if open_tickets >= 3:
            reasons.append("Multiple open tickets may indicate unresolved friction")
            recommendations.append("Prioritize unresolved employee tickets")

        snapshot = (
            self.db.query(RiskSnapshot)
            .filter(
                RiskSnapshot.user_id == user_id,
                RiskSnapshot.period_start == today,
                RiskSnapshot.period_end == today,
            )
            .first()
        )

        if not snapshot:
            snapshot = RiskSnapshot(user_id=user_id, period_start=today, period_end=today)
            self.db.add(snapshot)

        snapshot.engagement_score = round(engagement_score, 1)
        snapshot.mood_score = mood_score
        snapshot.burnout_risk = round(burnout_risk, 3)
        snapshot.attrition_risk = round(attrition_risk, 3)
        snapshot.silence_risk = round(silence_risk, 3)
        snapshot.confidence = round(confidence, 3)
        snapshot.risk_reasons = reasons
        snapshot.recommendations = recommendations
        return snapshot

    def capture_chat_signal(
        self,
        user_id: UUID,
        text: str,
        conversation_id: Optional[UUID] = None,
        source: str = "chat",
        sentiment_score_override: Optional[float] = None,
    ) -> Dict[str, Any]:
        sentiment = self.sentiment.analyze(text)
        score = float(sentiment_score_override if sentiment_score_override is not None else sentiment["score"])
        label = self._label_from_score(score)

        stress_indicator, burnout_indicator, detected_keywords = self._compute_stress_and_burnout(score, text)
        if stress_indicator >= 0.75 or score <= -0.7:
            triage = "high"
        elif stress_indicator >= 0.45 or score <= -0.35:
            triage = "watch"
        else:
            triage = "none"

        requires_followup = triage == "high"

        signal = WellbeingSignal(
            user_id=user_id,
            conversation_id=conversation_id,
            source=source,
            sentiment_label=label,
            sentiment_score=round(score, 3),
            stress_indicator=round(stress_indicator, 3),
            burnout_indicator=round(burnout_indicator, 3),
            triage_level=triage,
            requires_hr_followup=requires_followup,
            detected_keywords=detected_keywords,
            signal_metadata={"source": source},
        )
        self.db.add(signal)
        self.db.flush()

        self._create_hr_alert_if_needed(
            user_id=user_id,
            triage_level=triage,
            sentiment_score=score,
            text=text,
            signal_id=signal.id,
        )

        snapshot = self._upsert_daily_risk_snapshot(user_id=user_id)
        self.db.commit()

        return {
            "signal_id": str(signal.id),
            "sentiment_label": signal.sentiment_label,
            "sentiment_score": signal.sentiment_score,
            "stress_indicator": signal.stress_indicator,
            "burnout_indicator": signal.burnout_indicator,
            "triage_level": signal.triage_level,
            "requires_hr_followup": signal.requires_hr_followup,
            "risk_snapshot_id": str(snapshot.id),
        }

    def track_activity_event(
        self,
        user_id: UUID,
        event_type: str,
        event_source: str = "web",
        activity_state: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = utcnow_naive()
        event = ActivityEvent(
            user_id=user_id,
            event_type=event_type,
            event_source=event_source,
            activity_state=activity_state,
            event_at=now,
            event_metadata=metadata or {},
        )
        self.db.add(event)
        self.db.flush()

        nudge_message: Optional[str] = None
        if event_type in self.ACTIVE_EVENT_TYPES:
            window_start = now - timedelta(hours=2, minutes=30)
            active_count = (
                self.db.query(func.count(ActivityEvent.id))
                .filter(
                    ActivityEvent.user_id == user_id,
                    ActivityEvent.event_at >= window_start,
                    ActivityEvent.event_type.in_(list(self.ACTIVE_EVENT_TYPES)),
                )
                .scalar()
                or 0
            )
            break_count = (
                self.db.query(func.count(ActivityEvent.id))
                .filter(
                    ActivityEvent.user_id == user_id,
                    ActivityEvent.event_at >= window_start,
                    ActivityEvent.event_type.in_(list(self.BREAK_EVENT_TYPES)),
                )
                .scalar()
                or 0
            )

            if active_count >= 6 and break_count == 0:
                dedupe = (
                    self.db.query(AutomationAction)
                    .filter(
                        AutomationAction.rule_name == "break_reminder",
                        AutomationAction.user_id == user_id,
                        AutomationAction.created_at >= now - timedelta(hours=1),
                    )
                    .first()
                )
                if not dedupe:
                    if self._is_suppressed(
                        user_id=user_id,
                        action_type="nudge",
                        rule_name="break_reminder",
                        now=now,
                    ):
                        self.db.commit()
                        return {
                            "event_id": str(event.id),
                            "event_type": event.event_type,
                            "event_at": event.event_at.isoformat() if event.event_at else now.isoformat(),
                            "nudge": None,
                        }
                    candidate_message = "Hey, you've been active for a while. A quick break might help."
                    eligible, reason = self.decide_nudge_eligibility(
                        user_id=user_id,
                        nudge_type="break_reminder",
                        message=candidate_message,
                        now=now,
                    )
                    if eligible:
                        nudge_message = candidate_message
                        self.db.add(
                            AutomationAction(
                                rule_name="break_reminder",
                                user_id=user_id,
                                target_type="user",
                                action_type="nudge",
                                trigger_event_id=event.id,
                                trigger_context={
                                    "event_type": event_type,
                                    "active_count": active_count,
                                    "ai_gate_reason": reason,
                                },
                                status="sent",
                                executed_at=now,
                            )
                        )
                        self._publish_user_nudge(user_id, nudge_message, "break_reminder")

        self.db.commit()
        return {
            "event_id": str(event.id),
            "event_type": event.event_type,
            "event_at": event.event_at.isoformat() if event.event_at else now.isoformat(),
            "nudge": nudge_message,
        }

    def create_reminder(
        self,
        user_id: UUID,
        reminder_type: str,
        title: str,
        message: str,
        schedule_kind: str,
        run_at: Optional[datetime] = None,
        cron_expr: Optional[str] = None,
        timezone: str = "UTC",
        payload: Optional[Dict[str, Any]] = None,
    ) -> ReminderSchedule:
        now = utcnow_naive()
        schedule_kind = (schedule_kind or "one_time").lower()
        if schedule_kind not in {"one_time", "daily", "weekly", "cron"}:
            raise ValueError("Invalid schedule_kind")

        next_trigger_at: Optional[datetime] = run_at
        if schedule_kind == "one_time":
            if not run_at:
                raise ValueError("run_at is required for one_time reminders")
        elif schedule_kind == "daily":
            base = run_at or (now + timedelta(days=1))
            while base <= now:
                base = base + timedelta(days=1)
            next_trigger_at = base
        elif schedule_kind == "weekly":
            base = run_at or (now + timedelta(days=7))
            while base <= now:
                base = base + timedelta(days=7)
            next_trigger_at = base
        else:  # cron
            next_trigger_at = run_at or (now + timedelta(minutes=15))

        row = ReminderSchedule(
            user_id=user_id,
            reminder_type=reminder_type,
            title=title,
            message=message,
            schedule_kind=schedule_kind,
            run_at=run_at,
            cron_expr=cron_expr,
            timezone=timezone or "UTC",
            status="active",
            next_trigger_at=next_trigger_at,
            payload=payload or {},
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def schedule_medication_reminder(
        self,
        user_id: UUID,
        medication: str,
        run_at: datetime,
        *,
        daily: bool = True,
        timezone: str = "UTC",
    ) -> ReminderSchedule:
        """Convenience wrapper for a (typically recurring) medication reminder.

        Stores only the medication label + time — never a diagnosis — and rides
        the existing reminder pipeline (scheduler fires it; Phase 2 SSE delivers
        it live to the user's chat).
        """
        label = (medication or "your medication").strip()
        return self.create_reminder(
            user_id=user_id,
            reminder_type="medication",
            title=f"Medication: {label}",
            message=f"💊 Time to take {label}. Take care of yourself!",
            schedule_kind="daily" if daily else "one_time",
            run_at=run_at,
            timezone=timezone or "UTC",
            payload={"medication": label},
        )

    def list_reminders(self, user_id: UUID, include_cancelled: bool = False) -> List[ReminderSchedule]:
        q = self.db.query(ReminderSchedule).filter(ReminderSchedule.user_id == user_id)
        if not include_cancelled:
            q = q.filter(ReminderSchedule.status != "cancelled")
        return q.order_by(ReminderSchedule.created_at.desc()).all()

    def update_reminder(
        self,
        user_id: UUID,
        reminder_id: UUID,
        updates: Dict[str, Any],
    ) -> Optional[ReminderSchedule]:
        row = (
            self.db.query(ReminderSchedule)
            .filter(ReminderSchedule.id == reminder_id, ReminderSchedule.user_id == user_id)
            .first()
        )
        if not row:
            return None

        for key in [
            "title",
            "message",
            "status",
            "run_at",
            "cron_expr",
            "timezone",
            "payload",
            "schedule_kind",
            "next_trigger_at",
        ]:
            if key in updates and updates[key] is not None:
                setattr(row, key, updates[key])

        if row.status == "cancelled":
            row.next_trigger_at = None

        row.updated_at = utcnow_naive()
        self.db.commit()
        self.db.refresh(row)
        return row

    def cancel_reminder(self, user_id: UUID, reminder_id: UUID) -> bool:
        row = (
            self.db.query(ReminderSchedule)
            .filter(ReminderSchedule.id == reminder_id, ReminderSchedule.user_id == user_id)
            .first()
        )
        if not row:
            return False
        row.status = "cancelled"
        row.next_trigger_at = None
        row.updated_at = utcnow_naive()
        self.db.commit()
        return True

    def record_daily_checkin(
        self,
        user_id: UUID,
        mood: str,
        message: str,
        wants_followup: bool = False,
    ) -> Dict[str, Any]:
        mood_map = {
            "great": 0.8,
            "good": 0.35,
            "okay": 0.0,
            "low": -0.35,
            "stressed": -0.7,
        }
        baseline = mood_map.get((mood or "okay").lower(), 0.0)
        if message:
            analyzed = self.sentiment.analyze(message)
            score = baseline * 0.6 + float(analyzed["score"]) * 0.4
            text = message
        else:
            score = baseline
            text = f"Daily check-in mood: {mood}"

        signal = self.capture_chat_signal(
            user_id=user_id,
            text=text,
            conversation_id=None,
            source="daily_checkin",
            sentiment_score_override=score,
        )

        suggestion = "Thanks for checking in. I am here anytime you need support."
        if signal["triage_level"] == "high" or wants_followup:
            suggestion = "Thanks for sharing. I can nudge HR for a supportive check-in if you want."
            now = utcnow_naive()
            if not self._is_suppressed(
                user_id=user_id,
                action_type="followup_offer",
                rule_name="daily_checkin_followup",
                now=now,
            ):
                self.db.add(
                    AutomationAction(
                        rule_name="daily_checkin_followup",
                        user_id=user_id,
                        target_type="user",
                        action_type="followup_offer",
                        status="sent",
                        executed_at=now,
                        trigger_context={"triage_level": signal["triage_level"], "mood": mood},
                    )
                )
                self.db.commit()

        return {
            "mood": mood,
            "signal": signal,
            "suggested_next_step": suggestion,
        }

    def list_high_risk_users(self, limit: int = 25) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 100))

        latest = (
            self.db.query(
                RiskSnapshot.user_id.label("user_id"),
                func.max(RiskSnapshot.created_at).label("max_created"),
            )
            .group_by(RiskSnapshot.user_id)
            .subquery()
        )

        rows = (
            self.db.query(User, RiskSnapshot)
            .join(latest, latest.c.user_id == User.id)
            .join(
                RiskSnapshot,
                and_(
                    RiskSnapshot.user_id == latest.c.user_id,
                    RiskSnapshot.created_at == latest.c.max_created,
                ),
            )
            .filter(User.role == UserRole.employee, User.status == UserStatus.active)
            .order_by(func.coalesce(RiskSnapshot.attrition_risk, 0.0).desc())
            .limit(limit)
            .all()
        )

        result: List[Dict[str, Any]] = []
        now = utcnow_naive()
        for user, snapshot in rows:
            risk = float(snapshot.attrition_risk or 0.0)
            if risk >= 0.67:
                level = "high"
            elif risk >= 0.4:
                level = "medium"
            else:
                level = "low"

            last_active = (
                self.db.query(func.max(Message.created_at))
                .join(Conversation, Message.conversation_id == Conversation.id)
                .filter(Conversation.user_id == user.id, Message.sender == MessageSender.user)
                .scalar()
            )
            last_active_text = "Never"
            if last_active:
                mins = int((now - last_active).total_seconds() // 60)
                if mins < 2:
                    last_active_text = "Just now"
                elif mins < 60:
                    last_active_text = f"{mins} mins ago"
                elif mins < 24 * 60:
                    last_active_text = f"{mins // 60} hours ago"
                else:
                    last_active_text = f"{mins // (24 * 60)} days ago"

            open_tickets = (
                self.db.query(func.count(Ticket.id))
                .filter(
                    Ticket.user_id == user.id,
                    Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]),
                )
                .scalar()
                or 0
            )

            result.append(
                {
                    "user_id": str(user.id),
                    "name": user.name,
                    "mood_score": round(float(snapshot.mood_score or 0.0), 1),
                    "risk_score": round(risk * 100.0, 1),
                    "risk_level": level,
                    "open_tickets": int(open_tickets),
                    "last_active": last_active_text,
                    "reasons": snapshot.risk_reasons or [],
                }
            )

        return result

    def build_weekly_hr_summary(self) -> Dict[str, Any]:
        since = utcnow_naive() - timedelta(days=7)

        high_risk = (
            self.db.query(func.count(RiskSnapshot.id))
            .filter(RiskSnapshot.created_at >= since, RiskSnapshot.attrition_risk >= 0.67)
            .scalar()
            or 0
        )

        negative_signals = (
            self.db.query(func.count(WellbeingSignal.id))
            .filter(
                WellbeingSignal.computed_at >= since,
                WellbeingSignal.requires_hr_followup.is_(True),
            )
            .scalar()
            or 0
        )

        open_tickets = (
            self.db.query(func.count(Ticket.id))
            .filter(Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress, TicketStatus.escalated]))
            .scalar()
            or 0
        )

        top_issues = (
            self.db.query(Ticket.category, func.count(Ticket.id).label("count"))
            .filter(Ticket.created_at >= since)
            .group_by(Ticket.category)
            .order_by(func.count(Ticket.id).desc())
            .limit(5)
            .all()
        )

        avg_engagement = (
            self.db.query(func.avg(RiskSnapshot.engagement_score))
            .filter(RiskSnapshot.created_at >= since)
            .scalar()
        )

        return {
            "window_days": 7,
            "high_risk_employees": int(high_risk),
            "followup_signals": int(negative_signals),
            "open_tickets": int(open_tickets),
            "avg_engagement_score": round(float(avg_engagement or 0.0), 1),
            "top_issues": [{"category": c or "general", "count": int(n)} for c, n in top_issues],
        }

    def process_due_reminders(self, batch_size: int = 100) -> Dict[str, Any]:
        now = utcnow_naive()
        due_rows = (
            self.db.query(ReminderSchedule)
            .filter(
                ReminderSchedule.status == "active",
                ReminderSchedule.next_trigger_at.isnot(None),
                ReminderSchedule.next_trigger_at <= now,
            )
            .order_by(ReminderSchedule.next_trigger_at.asc())
            .limit(max(1, min(batch_size, 500)))
            .all()
        )

        processed = 0
        sent = 0
        for row in due_rows:
            if self._is_suppressed(
                user_id=row.user_id,
                action_type="reminder",
                rule_name="scheduled_reminder",
                now=now,
            ):
                row.next_trigger_at = now + timedelta(minutes=30)
                continue
            processed += 1
            self.db.add(
                AutomationAction(
                    rule_name="scheduled_reminder",
                    user_id=row.user_id,
                    target_type="user",
                    action_type="reminder",
                    status="sent",
                    scheduled_for=row.next_trigger_at,
                    executed_at=now,
                    trigger_context={
                        "reminder_id": str(row.id),
                        "title": row.title,
                        "reminder_type": row.reminder_type,
                    },
                )
            )
            sent += 1
            row.last_triggered_at = now
            action_url = (row.payload or {}).get("action_url") if isinstance(row.payload, dict) else None
            self._publish_user_nudge(
                row.user_id,
                row.message or row.title or "You have a reminder.",
                row.reminder_type or "scheduled_reminder",
                action_url=action_url,
            )

            if row.schedule_kind == "one_time":
                row.status = "cancelled"
                row.next_trigger_at = None
            elif row.schedule_kind == "daily" and row.next_trigger_at:
                row.next_trigger_at = row.next_trigger_at + timedelta(days=1)
            elif row.schedule_kind == "weekly" and row.next_trigger_at:
                row.next_trigger_at = row.next_trigger_at + timedelta(days=7)
            else:
                row.next_trigger_at = now + timedelta(days=1)

        self.db.commit()
        return {
            "processed": processed,
            "sent": sent,
            "checked_at": now.isoformat(),
        }


def get_mark_proactive_service(db: Session) -> MarkProactiveService:
    return MarkProactiveService(db)
