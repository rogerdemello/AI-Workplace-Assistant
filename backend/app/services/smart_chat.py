"""
SmartChatService - Core conversation AI service for the Friendly HR assistant.

This service orchestrates:
- Intent classification
- Sentiment analysis
- Context-aware response generation
- Emotional memory tracking
- RAG-based policy queries
"""

from typing import Dict, Optional, List, Iterator
from uuid import UUID
from sqlalchemy.orm import Session
import logging
import json
import re
from difflib import SequenceMatcher
from datetime import datetime, date, timedelta, timezone

from ..models.leave_request import LeaveRequest, LeaveStatus, LeaveType
from ..models.ticket import Ticket, TicketPriority, TicketStatus
from ..services.ticket import TicketService

from ..config import settings
from ..ai_client import get_ai_client, AzureOpenAIClient, MockAzureOpenAIClient
from ..core.feature_flags import get_feature_flags
from .intent_classifier import IntentClassifier, get_intent_classifier
from .sentiment import SentimentService
from .emotional_memory import EmotionalMemory, get_emotional_memory
from .memory_filters import should_store_memory
from .hr_personality import (
    FRIENDLY_SYSTEM_PROMPT,
    detect_conversation_mode,
    build_context_aware_prompt,
    get_conversation_starter,
    get_break_reminder,
    get_casual_joke,
)
from .chat.orchestrator import ConversationOrchestrator
from .rag.rag_orchestrator import RAGOrchestrator
from .entity_extractor import get_entity_extractor
from .health_detector import detect_health_keywords

logger = logging.getLogger(__name__)


def _fast_chat_enabled() -> bool:
    return bool(settings.FAST_CHAT_MODE)


class SmartChatService:
    """
    Core brain of the Friendly HR assistant.
    
    Handles the full conversation pipeline:
    1. Load user context
    2. Classify intent
    3. Analyze sentiment
    4. Generate response based on intent
    5. Update emotional memory
    6. Return response with metadata
    """
    
    # Greeting keywords for quick detection
    GREETING_KEYWORDS = [
        "hello", "hi", "hey", "good morning", "good afternoon",
        "good evening", "howdy", "hi there", "hello there",
        "how are you", "how's your day", "hows your day"
    ]
    
    SHORT_INPUT_KEYWORDS = [
        "yes", "yeah", "yep", "ok", "okay", "sure", "do it", "go ahead",
        "proceed", "continue", "please", "thanks", "thank you",
        "maybe", "later", "skip", "nah", "nope", "no"
    ]
    MEMORY_NOISE_KEYWORDS = {
        "yes", "yeah", "yep", "ok", "okay", "sure", "thanks", "thank you",
        "no", "nope", "nah", "fine", "cool", "great", "done"
    }
    LEAVE_BALANCE_KEYWORDS = (
        "how many leaves",
        "leave balance",
        "leaves left",
        "remaining leave",
        "how much leave",
        "leave days left",
    )
    
    # EAP resources for employee wellness support. Sourced from settings.EAP_RESOURCES_JSON
    # when set so deployers don't ship the bot quoting fake hotline numbers; falls back
    # to a public-helpline default below.
    EAP_DEFAULTS = {
        "hotline": "iCall (India): +91-9152987821",
        "website": "https://icallhelpline.org/",
        "confidential_note": "All EAP consultations are confidential. Your manager will not be notified.",
        "resources": [
            {
                "label": "iCall psychosocial helpline",
                "url": "https://icallhelpline.org/",
                "description": "Free, confidential counselling by trained mental-health professionals.",
            },
            {
                "label": "Talk to HR directly",
                "url": "mailto:hr@yourcompany.com",
                "description": "If you'd rather loop in HR, we'll keep it discreet.",
            },
        ],
    }

    @classmethod
    def _eap_config(cls) -> Dict:
        raw = (settings.EAP_RESOURCES_JSON or "").strip()
        if not raw:
            return cls.EAP_DEFAULTS
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            logger.warning("EAP_RESOURCES_JSON is not valid JSON; falling back to defaults")
            return cls.EAP_DEFAULTS
        if isinstance(parsed, list):
            return {**cls.EAP_DEFAULTS, "resources": parsed}
        if isinstance(parsed, dict):
            return {**cls.EAP_DEFAULTS, **parsed}
        return cls.EAP_DEFAULTS

    @property
    def EAP_RESOURCES(self) -> Dict:  # noqa: N802 — preserves existing call sites
        return self._eap_config()
    
    # Employee wellness tips for long sessions
    WELLNESS_TIPS = [
        "Remember to take short breaks every hour — stand up, stretch, and rest your eyes.",
        "Hydration matters! Keep a water bottle nearby.",
        "If you're feeling drained, a 5-minute walk can help reset focus.",
        "It's okay to step away and come back fresh. Take your time.",
    ]
    
    # Distress keywords that trigger EAP offering
    DISTRESS_KEYWORDS = [
        "stress", "anxious", "anxiety", "overwhelmed", "burnout", "burned out",
        "depressed", "depression", "sad", "hopeless", "tired", "exhausted",
        "panic", "panic attack", "heart racing", "can't sleep", "insomnia",
        "crying", "tears", "breakdown", "mental health", "therapy",
        "want to quit", "resign", "just quit", "had enough",
        "not okay", "not ok", "mentally", "emotional",
        "need a break", "i need a break", "need some time",
    ]
    
    # FAQ for new hires
    FAQ_ANSWERS = {
        # Company basics
        "who is the ceo": "Our CEO is Alex Thompson. He's been leading the company since 2020.",
        "who is the founder": "Our founder is Sarah Chen. She started the company in 2018.",
        "who founded the company": "Our founder is Sarah Chen. She started the company in 2018.",
        "what does the company do": "We're an AI-powered HR tech company helping businesses automate employee experience and engagement.",
        "what is the company": "We're an AI-powered HR tech company helping businesses automate employee experience and engagement.",
        "when was the company founded": "The company was founded in 2018 by Sarah Chen.",
        "where is the headquarters": "Our headquarters is in San Francisco, CA.",
        
        # Work policies
        "work from home": "Yes! We support flexible work arrangements. Talk to your manager about your WFH schedule.",
        "wfh policy": "Yes! We support flexible work arrangements. Talk to your manager about your WFH schedule.",
        "remote work": "Yes! We support flexible work arrangements. Talk to your manager about your WFH schedule.",
        "hybrid work": "We follow a hybrid model - typically 3 days in office, 2 days remote per week.",
        "office days": "We follow a hybrid model - typically 3 days in office, 2 days remote per week.",
        
        # Hours & attendance
        "work hours": "Standard work hours are 9 AM to 6 PM, but we're flexible! Core hours are 10 AM to 4 PM.",
        "what time do i start": "Standard work hours are 9 AM to 6 PM, but we're flexible! Core hours are 10 AM to 4 PM.",
        "dress code": "We have a casual dress code! Jeans and t-shirts are totally fine.",
        "what to wear": "We have a casual dress code! Jeans and t-shirts are totally fine.",
        
        # Time off
        "how many leaves do i have": "You get 24 days of paid time off per year, plus sick leave and holidays.",
        "leave policy": "You get 24 days of paid time off per year, plus sick leave and holidays.",
        "vacation days": "You get 24 days of paid time off per year, plus sick leave and holidays.",
        "pto": "You get 24 days of paid time off per year, plus sick leave and holidays.",
        "sick leave": "Yes, sick leave is separate from your PTO. Take care of yourself!",
        
        # Benefits
        "health insurance": "We offer comprehensive health, dental, and vision insurance for you and your family.",
        "benefits": "We offer health insurance, 401k matching, stock options, and many other perks!",
        "401k": "We offer 401k with 4% matching. Enroll through the benefits portal.",
        
        # IT & equipment
        "laptop": "IT will provide your laptop on your first day. Reach out to #it-help for setup.",
        "equipment": "IT will provide your laptop on your first day. Reach out to #it-help for setup.",
        "wifi password": "Connect to 'Infeedo-Guest' WiFi. The password changes monthly - ask your neighbor!",
        "email setup": "Your email should be ready on day 1. Check your inbox for welcome details.",
        
        # Getting started
        "first day": "On your first day, you'll meet your buddy, complete HR paperwork, and get your equipment set up.",
        "onboarding": "On your first day, you'll meet your buddy, complete HR paperwork, and get your equipment set up.",
        "who is my manager": "Check your offer letter or ask in #new-hires channel - your manager should have reached out!",
        "who is my buddy": "You'll be assigned a buddy on your first day. Check the #new-hires channel for introductions!",
        
        # Communication
        "slack": "Join #general, #random, #new-hires, and your team channel. We're very active on Slack!",
        "how to contact hr": "You can reach HR via the chat bot, email hr@infeedo.com, or post in #hr-questions.",
        "who do i talk to": "For questions, you can ask me, reach HR at hr@infeedo.com, or post in #hr-questions.",
        
        # Payroll
        "payday": "Payday is the 15th and last day of each month. If it falls on a weekend, you'll get it the Friday before.",
        "when do i get paid": "Payday is the 15th and last day of each month. If it falls on a weekend, you'll get it the Friday before.",
    }
    
    # Strong intent keywords that trigger flow switching when explicitly expressed
    STRONG_INTENT_KEYWORDS = {
        # Resignation / leaving role (not annual-leave / PTO)
        "leave the company": "resignation_support",
        "leave my job": "resignation_support",
        "quit my job": "resignation_support",
        "want to resign": "resignation_support",
        "want to quit": "resignation_support",
        "hand in my notice": "resignation_support",
        "give my notice": "resignation_support",
        "put in my notice": "resignation_support",
        # Ticket / complaint
        "raise ticket": "ticket_create",
        "raise complaint": "ticket_create",
        "file a complaint": "ticket_create",
        "file complaint": "ticket_create",
        "complaint": "ticket_create",
        "raise a ticket": "ticket_create",
        "ticket to hr": "ticket_create",
        "report issue": "ticket_create",
        "report a problem": "ticket_create",
        "complaint about": "ticket_create",
        "problem with my manager": "ticket_create",
        "issue with my manager": "ticket_create",
        # Escalate existing ticket
        "escalate my ticket": "escalate_ticket",
        "escalate the ticket": "escalate_ticket",
        "escalate ticket": "escalate_ticket",
        "please escalate": "escalate_ticket",
        # Leave apply
        "leave request": "leave_request",
        "apply leave": "leave_request",
        "apply for leave": "leave_request",
        "take time off": "leave_request",
        "time off": "leave_request",
        "request leave": "leave_request",
        "book leave": "leave_request",
        # Leave balance (query ONLY — must NOT start leave apply flow)
        "how many leaves": "leave_balance",
        "leave balance": "leave_balance",
        "leaves left": "leave_balance",
        "leaves remaining": "leave_balance",
        "leave days left": "leave_balance",
        "how much leave": "leave_balance",
        "remaining leave": "leave_balance",
        "leave quota": "leave_balance",
        # General conversation / context breakers (reset flow)
        "tell me a joke": "general_query",
        "joke": "general_query",
        "something funny": "general_query",
        "make me laugh": "general_query",
        "funny": "general_query",
        "weather": "general_query",
        "news": "general_query",
        "hi": "general_query",
        "hello": "general_query",
        "hey": "general_query",
        # Specific appreciation phrases — MUST come before the bare "thanks" /
        # "thank you" entries below so e.g. "thanks to Priya" routes to
        # appreciation, not the catch-all general_query.
        "thanks to": "appreciation",
        "thank you to": "appreciation",
        "shoutout to": "appreciation",
        "shout out to": "appreciation",
        "shout-out to": "appreciation",
        "kudos to": "appreciation",
        "credit to": "appreciation",
        "credit goes to": "appreciation",
        "hat tip to": "appreciation",
        "thanks": "general_query",
        "thank you": "general_query",
        "bye": "general_query",
        "goodbye": "general_query",
        "see you": "general_query",
    }

    # Mapping from intent to flow name (only intents that need a multi-step flow)
    INTENT_TO_FLOW = {
        "ticket_create": "ticket",
        "complaint": "ticket",
        "leave_request": "leave_request",
        "reminder": "reminder",
        "policy_query": "policy_query",
        "benefits_question": "benefits_question",
    }
    
    def __init__(
        self,
        db: Session,
        user_id: UUID,
        use_mock: bool = False,
        conversation_id: Optional[UUID] = None
    ):
        self.db = db
        self.user_id = user_id
        self.use_mock = use_mock
        self.conversation_id = conversation_id
        
        self.ai_client = get_ai_client(use_mock=use_mock)
        self.intent_classifier = get_intent_classifier(use_mock=use_mock)
        self.sentiment_service = SentimentService(db)
        self.emotional_memory = get_emotional_memory(db)
        self.entity_extractor = get_entity_extractor(use_mock=use_mock)
        
        self.user_context: Dict = {}
        self.conversation_state: str = "active"
        
        self.current_flow: Optional[str] = None
        self.previous_intent: Optional[str] = None
        self.conversation_mode: str = "assistant"
        self.flow_context: Dict = {}
        self.orchestrator = ConversationOrchestrator(self)
        
        self._load_user_context()
        if conversation_id:
            self._load_flow_state()
    
    def _load_user_context(self) -> None:
        try:
            self.user_context = self.emotional_memory.get_user_context(self.user_id)
        except Exception as e:
            logger.warning(f"Failed to load user context: {e}")
            self.user_context = {}
    
    def _load_flow_state(self) -> None:
        if not self.conversation_id:
            return
        try:
            from ..models.conversation import Conversation
            conv = self.db.query(Conversation).filter(
                Conversation.id == self.conversation_id
            ).first()
            if conv:
                self.current_flow = conv.active_flow
                self.previous_intent = conv.last_intent
                if conv.state:
                    self.flow_context = dict(conv.state)
                elif conv.flow_data:
                    self.flow_context = json.loads(conv.flow_data)
                self.conversation_mode = self.flow_context.get("conversation_mode", "assistant")
        except Exception as e:
            logger.warning(f"Failed to load flow state: {e}")

    def _save_flow_state(self) -> None:
        if not self.conversation_id:
            return
        try:
            from datetime import date, datetime
            from uuid import UUID as UUIDType

            def _json_sanitize(obj: object) -> object:
                if obj is None:
                    return None
                if isinstance(obj, UUIDType):
                    return str(obj)
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                if isinstance(obj, dict):
                    return {str(k): _json_sanitize(v) for k, v in obj.items()}
                if isinstance(obj, (list, tuple)):
                    return [_json_sanitize(x) for x in obj]
                if isinstance(obj, (str, int, float, bool)):
                    return obj
                return str(obj)

            from ..models.conversation import Conversation
            conv = self.db.query(Conversation).filter(
                Conversation.id == self.conversation_id
            ).first()
            if conv:
                conv.active_flow = self.current_flow
                conv.last_intent = self.previous_intent
                safe_ctx = _json_sanitize(self.flow_context) if self.flow_context else {}
                conv.state = safe_ctx if isinstance(safe_ctx, dict) else {}
                conv.last_question = self.flow_context.get("last_question")
                contract = self.flow_context.get("state_contract", {})
                conv.completed = bool(contract.get("completed", False))
                conv.flow_data = json.dumps(safe_ctx if isinstance(safe_ctx, dict) else {})
                self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to save flow state: {e}")
    
    def process_message(self, message: str) -> Dict:
        return self.orchestrator.run(message)

    def _apply_intent_keyword_fallback(self, classified_intent: str, message: str) -> str:
        """
        Guardrail for common classifier mistakes.
        Example: "How many leaves do I have left?" should never route to ticket flow.
        """
        msg = (message or "").strip().lower()
        if not msg:
            return classified_intent

        # Reminder keywords — high confidence regardless of classified intent
        if any(keyword in msg for keyword in ("set alarm", "set reminder", "remind me", "remind me to")):
            return "reminder"

        if classified_intent in {"ticket_create", "complaint"}:
            if any(keyword in msg for keyword in self.LEAVE_BALANCE_KEYWORDS):
                return "leave_balance"
        return classified_intent
    
    def _is_greeting(self, message: str) -> bool:
        message_lower = message.lower().strip()
        return any(
            message_lower == keyword or message_lower.startswith(f"{keyword} ")
            for keyword in self.GREETING_KEYWORDS
        )
    
    def _is_short_input(self, message: str) -> bool:
        normalized = message.strip().lower().strip(".!,")
        return normalized in self.SHORT_INPUT_KEYWORDS
    
    def eap_triggered(self, message: str) -> bool:
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.DISTRESS_KEYWORDS)
    
    def get_wellness_tip(self) -> str:
        import random
        return random.choice(self.WELLNESS_TIPS)

    def detect_faq(self, message: str) -> Optional[str]:
        message_lower = message.lower().strip()
        for question, answer in self.FAQ_ANSWERS.items():
            if question in message_lower:
                return answer
        return None

    def should_offer_wellness_tip(self, message_count: int) -> bool:
        """Determine if wellness tip should be offered based on conversation length."""
        return message_count > 0 and message_count % 15 == 0
    
    def _detect_strong_intent(self, message: str) -> Optional[str]:
        message_lower = message.lower()
        for keyword, intent in self.STRONG_INTENT_KEYWORDS.items():
            if keyword in message_lower:
                return intent
        return None
    
    def _get_flow_for_intent(self, intent: str) -> Optional[str]:
        return self.INTENT_TO_FLOW.get(intent)

    def _handle_greeting(self, sentiment: str, mode: str) -> str:
        """Handle greeting intents."""
        return get_conversation_starter(sentiment=sentiment, mode=mode)

    def _handle_help_request(self, message: str) -> str:
        text = (message or "").lower()
        if re.search(r"timesheet|time sheet|missing hours|submit hours|clock in|clock out", text):
            return "Got it — is this about filling your timesheet, fixing missing hours, or submitting it?"
        if re.search(r"email|mail|draft|write a note|recognition|appreciation", text):
            return "Sure — who is this for, and should it sound formal or casual?"
        if re.search(r"policy|leave policy|benefits|wfh|remote", text):
            return "Got it — is this about leave, benefits, or remote-work policy?"
        if re.search(r"ticket|complaint|issue|problem|manager", text):
            return "Understood — want me to raise this to HR now, or add more detail first?"
        return "Got it — do you want to complete a task, fix an issue, or ask a policy question?"

    def _handle_resignation_support(self, message: str) -> str:
        """Empathetic first response for someone considering leaving — not the same as booking PTO."""
        return (
            "I am really glad you said this here — that is a big thing to carry. "
            "If you are set on moving on, HR can walk you through notice, handover, and benefits smoothly. "
            "If something at work is pushing you to this, we can also help you talk it through or escalate safely. "
            "What feels most useful right now: **steps to resign**, or **talking about what is going on** before you decide?"
        )

    def _build_intent_switch_ack(self, from_flow: str, to_intent: str) -> str:
        from_label = from_flow.replace("_", " ")
        to_label = to_intent.replace("_", " ")
        return f"Got it, switching gears from {from_label} to {to_label}."

    def _try_fast_intent_reply(self, message: str) -> Optional[str]:
        """Short-circuit common phrasing without calling the general LLM (latency + consistency)."""
        if not _fast_chat_enabled():
            return None
        if self.current_flow in {"ticket", "leave_request"}:
            return None
        m = (message or "").strip().lower()
        if not m:
            return None
        if self._is_greeting(message) and len(m.split()) <= 4:
            return None
        if re.search(r"timesheet|time sheet|missing hours|submit hours|clock in|clock out", m):
            return "Got it — are you trying to fill it, fix missing hours, or submit it?"
        if re.search(r"appreciation|recognition|kudos|thank[- ]?you note|shout[- ]?out", m):
            return "Nice — should this be formal or casual?"
        if re.search(r"difficult 1:1|hard 1:1|tough conversation|difficult one[- ]on[- ]one|awkward 1:1", m):
            return "That sounds tough. Want help structuring the conversation so it stays calm and clear?"
        return None

    def _handle_emotional(self, message: str, sentiment: str) -> str:
        from .mental_health import create_risk_alert

        response = (
            "That sounds really tough. I'm here with you. "
            "Want me to help you structure what to say, or should I raise this with HR?"
        )

        if sentiment == "negative":
            try:
                create_risk_alert(
                    db=self.db,
                    user_id=self.user_id,
                    alert_type="emotional_distress",
                    severity="high",
                    title="Emotional distress detected in chat",
                    body=f"User expressed emotional distress: '{message[:200]}'. Sentiment: {sentiment}.",
                )
            except Exception as exc:
                logger.warning(f"Mental health alert creation skipped: {exc}")

        return response

    def _handle_leave_balance(self) -> str:
        """Answer 'how many leaves do I have left?' without starting leave apply flow."""
        import calendar
        from ..models.leave_request import LeaveRequest, LeaveStatus
        from datetime import date as _date

        year = _date.today().year
        # Count approved/pending leaves taken this calendar year
        taken_rows = (
            self.db.query(LeaveRequest)
            .filter(
                LeaveRequest.user_id == self.user_id,
                LeaveRequest.status.in_([LeaveStatus.approved, LeaveStatus.pending]),
                LeaveRequest.start_date >= _date(year, 1, 1),
            )
            .all()
        )
        days_taken = sum(
            max(0, (r.end_date - r.start_date).days + 1)
            for r in taken_rows
            if r.start_date and r.end_date
        )
        # Standard annual entitlement (can be made configurable)
        ANNUAL_ENTITLEMENT = 24
        remaining = max(0, ANNUAL_ENTITLEMENT - days_taken)
        pending = sum(1 for r in taken_rows if r.status == LeaveStatus.pending)

        if days_taken == 0:
            return (
                f"You haven't taken any leave yet this year 🎉 "
                f"You have **{ANNUAL_ENTITLEMENT} days** available. "
                f"Want to apply for some?"
            )
        msg = (
            f"You've used **{days_taken} of {ANNUAL_ENTITLEMENT} days** so far this year, "
            f"leaving **{remaining} days** to go."
        )
        if pending:
            msg += f" ({pending} leave request{'s' if pending > 1 else ''} still pending approval)"
        return msg

    def _handle_reminder(self, message: str) -> str:
        """Parse reminder request and create via mark_proactive_service."""
        import re
        from datetime import date as _date
        from ..services.mark_proactive import get_mark_proactive_service

        msg_lower = message.lower()

        # ── Parse time ──────────────────────────────────────────────
        time_match = re.search(
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", msg_lower, re.IGNORECASE
        )
        hour, minute = 9, 0  # sensible default
        if time_match:
            h = int(time_match.group(1))
            m = int(time_match.group(2) or 0)
            ampm = (time_match.group(3) or "").lower()
            if ampm == "pm" and h < 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0
            hour, minute = h, m

        # ── Auto-correct invalid times ──────────────────────────────
        if minute > 59:
            hour += minute // 60
            minute = minute % 60
        if hour > 23:
            hour = hour % 24
        if hour < 0:
            hour = 0
        if minute < 0:
            minute = 0

        time_str = f"{hour:02d}:{minute:02d}"

        # ── Detect recurrence ───────────────────────────────────────
        is_daily = any(w in msg_lower for w in ["every day", "everyday", "daily", "each day"])
        is_weekday = any(w in msg_lower for w in ["weekday", "working day", "monday to friday"])

        # ── Build cron / schedule ───────────────────────────────────
        if is_daily or is_weekday:
            cron_expr = f"{minute} {hour} * * {'1-5' if is_weekday else '*'}"
            schedule_kind = "cron"
            freq_label = "weekdays" if is_weekday else "daily"
        else:
            # One-time: next occurrence of the specified time today or tomorrow
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            cron_expr = None
            schedule_kind = "one_time"
            freq_label = f"once at {time_str}"

        # ── Extract reminder title from message ─────────────────────
        cleaned = re.sub(
            r"set (an? )?|remind me (to |about )?|alarm (for |at )?|reminder (for |at )?|every ?day|everyday|daily|at \d+.*",
            "", msg_lower
        ).strip()
        title = cleaned.capitalize() or "Custom reminder"
        if len(title) < 3:
            title = "Reminder"

        try:
            svc = get_mark_proactive_service(self.db)
            svc.create_reminder(
                user_id=self.user_id,
                reminder_type="custom",
                title=title,
                message=f"Hey! Reminder: {title} ⏰",
                schedule_kind=schedule_kind,
                cron_expr=cron_expr,
                run_at=target if schedule_kind == "one_time" else None,  # type: ignore[possibly-undefined]
                timezone="UTC",
                payload={"source": "chat"},
            )
            if is_daily or is_weekday:
                return (
                    f"Done! ✅ I've set a **{freq_label} reminder at {time_str}** for \"{title}\". "
                    f"You'll see it in your reminders panel — you can pause or cancel it any time."
                )
            else:
                return (
                    f"Sorted! ✅ I've set a **one-time reminder at {time_str}** for \"{title}\". "
                    f"Check the reminders panel anytime."
                )
        except Exception as exc:
            logger.error(f"Reminder creation failed: {exc}")
            return (
                f"Almost! I couldn't save the reminder right now (system hiccup 😬). "
                f"Try again or use the reminders panel directly."
            )

    def _normalize_leave_type(self, leave_type: Optional[str]) -> LeaveType:
        value = (leave_type or "paid").strip().lower().replace("-", " ")
        mapping = {
            "vacation": "paid",
            "annual": "paid",
            "annual leave": "paid",
            "paid leave": "paid",
            "sick": "sick",
            "sick leave": "sick",
            "work from home": "work_from_home",
            "wfh": "work_from_home",
            "remote": "work_from_home",
            "personal": "unpaid",
            "parental": "unpaid",
            "bereavement": "unpaid",
        }
        normalized = mapping.get(value, value.replace(" ", "_"))
        if normalized not in {leave.value for leave in LeaveType}:
            normalized = "paid"
        return LeaveType(normalized)

    def _coerce_date(self, value: object) -> Optional[date]:
        if isinstance(value, date):
            # Validate year range for date objects too
            if value.year < 2000 or value.year > 2100:
                return None
            return value
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
                # Reject impossible years — catches typos like 5555, 3423, 5
                if parsed.year < 2000 or parsed.year > 2100:
                    logger.warning(f"Rejected out-of-range date: {value} (year {parsed.year})")
                    return None
                return parsed
            except Exception:
                return None
        return None

    def _check_leave_overlap(self, leave_data: Dict):
        start = self._coerce_date(leave_data.get("start_date"))
        end = self._coerce_date(leave_data.get("end_date"))
        if not start or not end:
            return None
        return (
            self.db.query(LeaveRequest)
            .filter(
                LeaveRequest.user_id == self.user_id,
                LeaveRequest.status.in_([LeaveStatus.pending, LeaveStatus.approved]),
                LeaveRequest.start_date <= end,
                LeaveRequest.end_date >= start,
            )
            .first()
        )
    
    def _complete_leave(self, leave_data: Dict) -> str:
        start = self._coerce_date(leave_data.get("start_date"))
        end = self._coerce_date(leave_data.get("end_date"))

        if not start or not end:
            return "Almost there — just need both dates in YYYY-MM-DD format to submit."

        if end < start:
            return "The end date looks earlier than the start date. Can you double-check the end date?"

        from datetime import date as _date
        if start < _date.today() - timedelta(days=1):
            return "Start dates can't be more than 1 day in the past. Please use today or a future date."

        days = (end - start).days + 1
        if days > 60 and not self.flow_context.get("leave_long_duration_confirmed"):
            self.flow_context["leave_long_duration_warning_shown"] = True
            self.flow_context["last_question"] = "long_duration_warning"
            return (
                f"That's a {days}-day leave request. Long leaves usually need extra approval. "
                "Are you sure you want to proceed?"
            )

        overlap = self._check_leave_overlap(leave_data)
        if overlap:
            return (
                f"You already have leave from {overlap.start_date} to {overlap.end_date}. "
                "Do you still want to proceed?"
            )

        if start < _date.today():
            logger.info(f"Backdated leave request from user {self.user_id}: {start} to {end}")

        leave_type = self._normalize_leave_type(leave_data.get("leave_type"))

        leave_request = LeaveRequest(
            user_id=self.user_id,
            start_date=start,
            end_date=end,
            leave_type=leave_type,
            reason=leave_data.get("reason"),
            status=LeaveStatus.pending,
        )
        self.db.add(leave_request)

        # Retry commit with exponential backoff for transient DB errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.db.commit()
                break
            except Exception as exc:
                self.db.rollback()
                if attempt < max_retries - 1:
                    wait = 0.2 * (2 ** attempt)
                    logger.warning(f"Leave commit failed (attempt {attempt + 1}), retrying in {wait}s: {exc}")
                    import time
                    time.sleep(wait)
                else:
                    logger.error(f"Leave creation failed after {max_retries} attempts: {exc}")
                    return "Something went wrong saving your leave request. Please try again."

        self._reset_flow()
        reason_text = leave_data.get("reason") or ""
        empathy = ""
        if any(k in reason_text.lower() for k in ("fever", "sick", "ill", "unwell", "flu", "cold", "not feeling")):
            empathy = " Take care and get well soon. 🩹"
        return (
            f"Done! {days}-day {leave_type.value.replace('_', ' ')} leave from "
            f"{start} to {end} submitted. Your manager will review it soon. 🗓️{empathy}"
        )
    
    def _handle_policy_query(self, message: str) -> str:
        """Handle policy query using RAG."""
        if not get_feature_flags().enable_rag:
            return (
                "Looks like policy search is off right now. "
                "Tell me if it's leave, remote work, payroll, or benefits — I'll share the usual gist, or loop in HR."
            )

        if _fast_chat_enabled():
            faq_hit = self.detect_faq(message)
            if faq_hit:
                return faq_hit
            ml = (message or "").lower()
            if any(k in ml for k in ("leave policy", "pto policy", "vacation policy", "how many leave")):
                return (
                    "Looks like I can't pull the handbook right now — generally, paid leave needs your manager's approval. "
                    "Want HR to confirm the exact wording for you?"
                )
            if any(k in ml for k in ("remote", "wfh", "work from home", "hybrid")):
                return (
                    "I can't load the doc right now — most teams allow flexible WFH with your manager's alignment. "
                    "Want me to flag HR to confirm your team's rule?"
                )
            if any(k in ml for k in ("payroll", "pay day", "payday", "salary")):
                return (
                    "Docs are slow to load — payroll dates depend on your payroll calendar (often mid-month and month-end). "
                    "Want a quick HR ticket to confirm yours?"
                )
            if "benefit" in ml or "insurance" in ml or "401" in ml:
                return (
                    "I can't pull benefits text right now — your portal usually has the latest. "
                    "Want me to connect you to HR for specifics?"
                )
            return (
                "Looks like I can't pull that policy right now. "
                "Tell me if it's about leave, remote work, payroll, or benefits — I'll give the usual gist, or loop in HR for the official line."
            )

        try:
            result = RAGOrchestrator(self.db, use_mock=self.use_mock).ask(message)

            response = result.get("answer", "")
            citations = result.get("citations", [])

            if citations:
                # Render as a "Sources:" footer with bullet items rather than
                # bracketed inline text — much easier to scan and matches the
                # source-attribution UX promised in the roadmap.
                # Dedupe in case the LLM cited the same chunk twice.
                seen = []
                for c in citations:
                    if c and c not in seen:
                        seen.append(c)
                if seen:
                    response += "\n\nSources:\n" + "\n".join(f"• {c}" for c in seen)

            return response
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return (
                "Happy to help with that policy question. "
                "Give me a moment and I'll look it up for you."
            )
    
    def _handle_benefits_query(self, message: str) -> str:
        """Handle benefits questions using RAG."""
        return self._handle_policy_query(message)

    # Patterns to extract the colleague being thanked. Lead-in keywords are
    # case-insensitive (Thanks / THANKS / thanks all match); the captured name
    # still expects capital-cased proper-name form so we don't grab connectives.
    _APPRECIATION_TARGET_PATTERNS = (
        r"(?i:\bthanks?\s+to)\s+([A-Z][A-Za-z]{1,30}(?:\s+[A-Z][A-Za-z]{1,30})?)",
        r"(?i:\bthank\s+you)(?i:\s+to)?\s+([A-Z][A-Za-z]{1,30}(?:\s+[A-Z][A-Za-z]{1,30})?)",
        r"(?i:\bappreciat\w+\s+(?:goes\s+)?(?:to|for))\s+([A-Z][A-Za-z]{1,30}(?:\s+[A-Z][A-Za-z]{1,30})?)",
        r"(?i:\bshout[-\s]?out\s+to)\s+([A-Z][A-Za-z]{1,30}(?:\s+[A-Z][A-Za-z]{1,30})?)",
        r"(?i:\bkudos\s+to)\s+([A-Z][A-Za-z]{1,30}(?:\s+[A-Z][A-Za-z]{1,30})?)",
        r"(?i:\bcredit\s+(?:goes\s+)?to)\s+([A-Z][A-Za-z]{1,30}(?:\s+[A-Z][A-Za-z]{1,30})?)",
        r"(?i:\bhat\s+tip\s+to)\s+([A-Z][A-Za-z]{1,30}(?:\s+[A-Z][A-Za-z]{1,30})?)",
        r"\b([A-Z][A-Za-z]{1,30}(?:\s+[A-Z][A-Za-z]{1,30})?)\s+(?i:(?:really\s+|absolutely\s+)?(?:helped|saved|covered|carried|crushed\s+it))",
    )

    def _extract_appreciation_target(self, message: str) -> Optional[str]:
        for pattern in self._APPRECIATION_TARGET_PATTERNS:
            m = re.search(pattern, message)
            if m:
                return m.group(1).strip()
        return None

    def _find_user_by_name_or_email(self, query: str) -> "Optional[User]":
        from ..models.user import User as _User
        q = (query or "").strip()
        if not q:
            return None
        if "@" in q:
            return self.db.query(_User).filter(_User.email == q.lower()).first()
        # Name match: full-text-ish ILIKE. Prefer exact name first.
        exact = self.db.query(_User).filter(_User.name.ilike(q)).first()
        if exact:
            return exact
        return self.db.query(_User).filter(_User.name.ilike(f"%{q}%")).first()

    def _handle_appreciation(self, message: str) -> str:
        """Detect a gratitude-toward-a-colleague message and send a real note.

        Pending target is stashed in flow_context so a follow-up like "Priya"
        completes the send without retyping the whole phrase.
        """
        from ..models.appreciation_note import AppreciationNote

        # If we asked "who?" last turn, the new message IS the target.
        pending = self.flow_context.pop("_pending_appreciation", None) if self.flow_context else None
        target_name = None
        if pending:
            target_name = message.strip().rstrip("!.?")
        else:
            target_name = self._extract_appreciation_target(message)

        if not target_name:
            self.flow_context["_pending_appreciation"] = True
            return "Love that. Who should I send the appreciation to? Their name or email works."

        target_user = self._find_user_by_name_or_email(target_name)
        if not target_user:
            self.flow_context["_pending_appreciation"] = True
            return (
                f"I couldn't find someone named '{target_name}' in the directory. "
                "Could you share their email so I can route the note?"
            )
        if target_user.id == self.user_id:
            return "Self-appreciation noted 😊 — but a note is meant for someone else. Who actually helped you out?"

        try:
            note_text = message.strip()[:500] or f"Appreciation from a teammate."
            self.db.add(
                AppreciationNote(
                    from_user_id=self.user_id,
                    to_user_id=target_user.id,
                    message=note_text,
                    is_anonymous=False,
                )
            )
            self.db.commit()
        except Exception as exc:
            logger.warning("Appreciation note write failed: %s", exc, exc_info=True)
            try:
                self.db.rollback()
            except Exception:
                pass
            return "I tried to send that note but hit a snag — give me a moment and try again."

        first = (target_user.name or "").split()[0] if target_user.name else "them"
        return f"Sent — {first} will see your appreciation note 🙌"

    def _handle_escalate_ticket(self) -> str:
        """Find the user's most recent open ticket and escalate it."""
        ticket = (
            self.db.query(Ticket)
            .filter(Ticket.user_id == self.user_id)
            .filter(Ticket.status.in_([TicketStatus.open, TicketStatus.in_progress]))
            .order_by(Ticket.created_at.desc())
            .first()
        )
        if not ticket:
            return (
                "I don't see an open ticket to escalate. "
                "If you have a new issue, I can help you raise a ticket."
            )

        ticket_service = TicketService(self.db)
        updated = ticket_service.update_ticket(
            ticket_id=ticket.id,
            user_id=self.user_id,
            priority=TicketPriority.critical,
            status=TicketStatus.escalated,
        )
        if updated:
            ticket_service.add_message(
                ticket_id=ticket.id,
                sender_id=self.user_id,
                message_text="Ticket escalated by user via chat.",
            )
            ref = str(ticket.id)[:8]
            return (
                f"Done. I've escalated your ticket #{ref} to critical priority "
                f"and flagged it for immediate attention."
            )
        return "Something went wrong while escalating. Please try again."
    
    def _handle_email_draft(self, message: str) -> str:
        """Handle email draft requests."""
        if _fast_chat_enabled():
            return "Got it — I'll shape this for your audience. Should the tone be formal or friendly?"
        return "I can draft that for you. Who is the email for?"

    def _parse_yes_no(self, message: str) -> Optional[bool]:
        normalized = message.strip().lower().strip(".!,")
        yes_values = {
            "yes", "yeah", "yep", "sure", "okay", "ok", "please", "go ahead", "do it"
        }
        no_values = {
            "no", "nope", "nah", "skip", "later", "not now"
        }

        if normalized in yes_values:
            return True
        if normalized in no_values:
            return False

        if "keep it anonymous" in normalized or "stay anonymous" in normalized or normalized == "anonymous":
            return True
        if "not anonymous" in normalized or "do not keep anonymous" in normalized or normalized == "public":
            return False

        return None

    def _looks_like_ticket_issue(self, message: str) -> bool:
        text = message.strip()
        if len(text) >= 28:
            return True
        return bool(re.search(r"manager|harass|issue|problem|unfair|frustrat|payroll|policy|ticket|complaint", text, re.IGNORECASE))

    def _infer_ticket_severity(self, ticket_data: Dict) -> str:
        """Classify severity from collected text and optional intelligence — not from a user pick-one step."""
        blob = " ".join(
            str(x).strip()
            for x in (
                ticket_data.get("issue"),
                ticket_data.get("against"),
                ticket_data.get("details"),
            )
            if x
        )
        from_msg = self._extract_ticket_severity(blob)
        if from_msg:
            return from_msg
        intel = self.flow_context.get("_intelligence_sentiment") or {}
        label = str(intel.get("label", "")).lower()
        try:
            score = int(intel.get("score_0_100", 50))
        except (TypeError, ValueError):
            score = 50
        if label in ("negative", "very_negative") or score < 38:
            return "serious"
        return "mild"

    def _complete_ticket(self, ticket_data: Dict) -> str:
        # Ensure anonymous defaults to False if not set
        if ticket_data.get("anonymous") is None:
            ticket_data["anonymous"] = False

        dept = ticket_data.get("department") or "HR"
        issue = ticket_data.get("issue", "your concern")
        details = ticket_data.get("details")
        against = ticket_data.get("against")
        severity = self._infer_ticket_severity(ticket_data)
        ticket_data["severity"] = severity
        anon = bool(ticket_data.get("anonymous", False))

        category_map = {
            "hr": "hr",
            "it": "it",
            "facilities": "facilities",
            "finance": "finance",
            "management": "management",
        }
        category = category_map.get(str(dept).strip().lower(), "hr")

        query_parts = [str(issue).strip()]
        if severity:
            query_parts.append(f"Severity: {severity}")
        if against:
            query_parts.append(f"Against: {against}")
        if details:
            query_parts.append(f"Details: {details}")
        query_text = "\n".join([part for part in query_parts if part])

        priority = TicketPriority.medium
        if severity == "urgent" or re.search(r"urgent|harass|unsafe|threat|violence|discriminat", query_text, re.IGNORECASE):
            priority = TicketPriority.high
        elif severity == "mild":
            priority = TicketPriority.low

        ticket_service = TicketService(self.db)
        ticket, is_new = ticket_service.create_ticket_with_dedup(
            user_id=self.user_id,
            query=query_text,
            category=category,
            priority=priority,
            is_anonymous=anon,
        )

        if not is_new:
            self._reset_flow()
            ref = str(ticket.id)[:8]
            return (
                f"It looks like you already have something similar open (#{ref}). "
                f"I didn't create a duplicate. Want me to add a follow-up there?"
            )

        ticket_ref = str(ticket.id)[:8]
        self.flow_context["last_ticket_id"] = str(ticket.id)

        # Reset flow state cleanly
        self._reset_flow()

        if anon:
            return (
                f"Done - I've shared this with HR (reference #{ticket_ref}).\n"
                "This will be handled confidentially, and they'll follow up.\n"
                "If you want to add anything later, I'm here."
            )
        return (
            f"Done - I've shared this with HR (reference #{ticket_ref}).\n"
            "They'll review it and get back to you.\n"
            "If anything else comes up, you can tell me anytime."
        )

    def _extract_ticket_severity(self, message: str) -> Optional[str]:
        text = (message or "").lower()
        if any(word in text for word in ["urgent", "critical", "immediate", "asap"]):
            return "urgent"
        if any(word in text for word in ["serious", "severe", "major"]):
            return "serious"
        if any(word in text for word in ["mild", "minor", "small"]):
            return "mild"
        return None
    
    def _recent_messages_for_llm(self, limit: int = 8) -> List[Dict[str, str]]:
        """Recent persisted turns in chronological order as LLM message dicts.

        Without this MARK forgets what was just said — "yeah" after empathy reads
        as a fresh greeting because only the current message reaches the model.
        """
        if not self.conversation_id:
            return []
        try:
            from ..models.conversation import Message, MessageSender as _MS
            from sqlalchemy import desc as _desc
            rows = (
                self.db.query(Message)
                .filter(Message.conversation_id == self.conversation_id)
                .order_by(_desc(Message.created_at))
                .limit(max(1, int(limit)))
                .all()
            )
            history: List[Dict[str, str]] = []
            for m in reversed(rows):  # oldest first for the model
                text = (m.message_text or "").strip()
                if not text:
                    continue
                role = "user" if m.sender == _MS.user else "assistant"
                history.append({"role": role, "content": text})
            return history
        except Exception as exc:
            logger.warning(f"Failed to load conversation history for LLM: {exc}")
            return []

    def _handle_general_query(self, message: str, sentiment: str, mode: str) -> str:
        """Handle general queries using AI."""
        try:
            # Build context-aware prompt
            user_name = self.user_context.get("user_name")
            recent_sentiment = self.user_context.get("current_mood")
            department = self.user_context.get("department")

            system_prompt = build_context_aware_prompt(
                user_name=user_name,
                recent_sentiment=recent_sentiment,
                department_context=department,
                mode=mode,
            )

            history = self._recent_messages_for_llm(limit=8)
            response = self.ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    *history,
                    {"role": "user", "content": message},
                ],
                temperature=0.4,
                max_tokens=140
            )

            return response["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            return (
                "I am here for you. "
                "What do you want to get done right now?"
            )

    def stream_general_query_tokens(self, message: str, sentiment: str, mode: str):
        """Yield true model tokens for general chat responses."""
        user_name = self.user_context.get("user_name")
        recent_sentiment = self.user_context.get("current_mood")
        department = self.user_context.get("department")
        system_prompt = build_context_aware_prompt(
            user_name=user_name,
            recent_sentiment=recent_sentiment,
            department_context=department,
            mode=mode,
        )
        history = self._recent_messages_for_llm(limit=8)
        return self.ai_client.chat_completion_stream(
            messages=[
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": message},
            ],
            temperature=0.4,
            max_tokens=140,
            deployment=settings.AZURE_OPENAI_FAST_DEPLOYMENT or None,
        )

    def stream_non_flow_intent_tokens(self, intent: str, message: str, sentiment: str, mode: str):
        """Yield model tokens for safe non-flow intents."""
        intent_key = (intent or "general_query").strip().lower()
        if intent_key == "general_query":
            return self.stream_general_query_tokens(message=message, sentiment=sentiment, mode=mode)

        if intent_key == "help_request":
            system_prompt = (
                f"{FRIENDLY_SYSTEM_PROMPT}\n"
                "Reply in 1-2 short lines. Be specific and action-oriented. "
                "Ask exactly one clear next-step question."
            )
            return self.ai_client.chat_completion_stream(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                temperature=0.3,
                max_tokens=120,
                deployment=settings.AZURE_OPENAI_FAST_DEPLOYMENT or None,
            )

        if intent_key == "email_draft":
            system_prompt = (
                f"{FRIENDLY_SYSTEM_PROMPT}\n"
                "You are helping draft workplace emails. "
                "Reply in 1-2 short lines and ask one targeted clarification "
                "(audience and tone) if missing."
            )
            return self.ai_client.chat_completion_stream(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                temperature=0.35,
                max_tokens=140,
                deployment=settings.AZURE_OPENAI_FAST_DEPLOYMENT or None,
            )

        if intent_key in {"policy_query", "benefits_question"}:
            return self.stream_policy_query_tokens(message=message)

        return self.stream_general_query_tokens(message=message, sentiment=sentiment, mode=mode)

    def stream_policy_query_tokens(self, message: str) -> Iterator[str]:
        """
        Stream policy answers for RAG intents.

        Today this streams token-like chunks from the RAG answer text so the UI
        gets progressive updates while preserving the existing policy fallback behavior.
        """
        answer = self._handle_policy_query(message)
        words = [word for word in str(answer).split(" ") if word]
        if not words:
            yield str(answer)
            return
        for word in words:
            yield f"{word} "

    def _deduplicate_response(self, response_text: str) -> str:
        text = (response_text or "").strip().lower()
        response_hash = hash(text)
        last_hash = self.flow_context.get("last_response_hash")
        if response_hash == last_hash and text:
            response_text = response_text + " Let me know if you need anything else."
        self.flow_context["last_response_hash"] = response_hash
        return response_text

    def _strip_robotic_phrasing(self, text: str) -> str:
        replacements = {
            "i can help you with that": "Got it",
            "please provide more details": "Can you share a bit more detail?",
            "please provide details": "Can you share a bit more detail?",
            "kindly specify": "Can you clarify",
            "how may i assist you": "What do you want to do next?",
        }
        output = text
        for old, new in replacements.items():
            output = re.sub(old, new, output, flags=re.IGNORECASE)
        return output

    def _finalize_response(
        self,
        response: str,
        intent: str,
        sentiment: str,
        mode: str,
        message_count: int = 0,
        source_message: str = "",
    ) -> str:
        cleaned = " ".join((response or "").split())
        cleaned = self._strip_robotic_phrasing(cleaned)
        if not cleaned:
            return "I am here with you. What do you need right now?"

        # Preserve ticket references before truncating
        ticket_ref_match = re.search(r"Reference:\s*#[A-Za-z0-9\-]+", cleaned)
        ticket_ref = ticket_ref_match.group(0) if ticket_ref_match else None

        if mode == "support" and not self._has_empathy_prefix(cleaned):
            prefix = "That sounds hard."
            if sentiment == "negative":
                prefix = "That sounds really frustrating."
            cleaned = f"{prefix} {cleaned}"

        sentence_limit = 3 if intent in {"policy_query", "benefits_question"} else 2
        cleaned = self._limit_sentences(cleaned, sentence_limit)
        cleaned = self._ensure_single_question(cleaned)

        if len(cleaned) > 420:
            cleaned = cleaned[:419].rstrip() + "."

        # Append ticket reference back if it was truncated out
        if ticket_ref and ticket_ref not in cleaned:
            cleaned = f"{cleaned}\n{ticket_ref}"

        if sentiment == "negative":
            cleaned = self._append_eap_offer(cleaned, source_message=source_message)

        if self.should_offer_wellness_tip(message_count):
            cleaned = f"{cleaned} {self.get_wellness_tip()}"

        return cleaned
    
    def _append_eap_offer(self, response: str, source_message: str = "") -> str:
        if not self.eap_triggered(source_message):
            return response
        eap_msg = (
            f"\n\nIf things feel heavy, you can reach out to our EAP hotline "
            f"({self.EAP_RESOURCES['hotline']}) — it's confidential."
        )
        return response + eap_msg

    def _has_empathy_prefix(self, text: str) -> bool:
        lowered = text.lower()
        empathy_markers = [
            "that sounds",
            "i hear you",
            "i have got you",
            "i've got you",
            "thanks for sharing",
            "sorry this happened",
        ]
        return any(marker in lowered for marker in empathy_markers)

    def _limit_sentences(self, text: str, limit: int) -> str:
        parts = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", text) if segment.strip()]
        if len(parts) <= limit:
            return text.strip()
        return " ".join(parts[:limit]).strip()

    def _ensure_single_question(self, text: str) -> str:
        if text.count("?") <= 1:
            return text

        first_question_index = text.find("?")
        head = text[: first_question_index + 1]
        tail = text[first_question_index + 1 :].replace("?", ".")
        return f"{head}{tail}"
    
    def _update_conversation_state(self, intent: str, message: str) -> None:
        """Update conversation state based on intent and message flow."""
        # Check for multi-turn flow indicators
        message_lower = message.lower()
        
        if intent == "leave_request":
            if any(kw in message_lower for kw in ["dates", "next week", "tomorrow", "taking off"]):
                self.conversation_state = "leave_dates_collected"
            else:
                self.conversation_state = "collecting_leave_details"
        
        elif intent == "ticket_create":
            if any(kw in message_lower for kw in ["issue", "problem", "help"]):
                self.conversation_state = "collecting_ticket_details"
            else:
                self.conversation_state = "active"
        
        elif intent == "email_draft":
            self.conversation_state = "collecting_email_details"

        elif self.conversation_mode == "support":
            self.conversation_state = "support_mode"

        elif self.conversation_mode == "action":
            self.conversation_state = "action_mode"
        
        else:
            self.conversation_state = "active"
    
    def _compress_response(self, response: str, intent: str, sentiment: str) -> str:
        """Compress long responses to be more human-like."""
        # Use regex to split on sentence boundaries (avoids mid-word splits on dots in abbreviations)
        sentence_pattern = re.compile(r'(?<=[.!?])\s+')
        sentences = [s.strip() for s in sentence_pattern.split(response.strip()) if s.strip()]
        sentence_count = len(sentences)

        # Already short enough
        if sentence_count <= 3:
            return response

        # Preserve responses containing ticket references
        if re.search(r"Reference:\s*#[A-Za-z0-9\-]+", response):
            return response

        # For emotional/complaint content — call AI to compress more naturally
        if sentiment == "negative" or intent in ["complaint", "general_query"]:
            try:
                compress_prompt = (
                    f'Rewrite this to be SHORT (1–2 sentences), warm, and human-like. '
                    f'End with one question if appropriate.\n\n"{response[:500]}"'
                )
                result = self.ai_client.chat_completion(
                    messages=[
                        {"role": "system", "content": "You rewrite text to be short and human-like."},
                        {"role": "user", "content": compress_prompt}
                    ],
                    temperature=0.5,
                    max_tokens=120
                )
                compressed = result["choices"][0]["message"]["content"]
                if compressed and len(compressed) > 10:
                    return compressed.strip()
            except Exception as e:
                logger.warning(f"Response compression failed: {e}")

        # Fallback: join first 2 sentences cleanly
        return " ".join(sentences[:2])
    
    def _reset_flow(self) -> None:
        """Clear active conversational flow state and persist the reset."""
        self.current_flow = None
        self.flow_context = {}
        self.previous_intent = None
        self._save_flow_state()

    def _update_memory(
        self,
        message: str,
        intent: str,
        sentiment: str
    ) -> None:
        """Update emotional memory with the current interaction."""
        if not should_store_memory(message, intent=intent, sentiment=sentiment):
            return
        # Emotional memory is primarily tracked via message persistence.
        # If a recorder exists in future implementations, safely call it.
        recorder = getattr(self.emotional_memory, "record_interaction", None)
        if callable(recorder):
            try:
                recorder(
                    user_id=self.user_id,
                    message=message,
                    intent=intent,
                    sentiment=sentiment,
                )
            except Exception as exc:
                logger.warning(f"Emotional memory update skipped: {exc}")
    
    def _empty_message_response(self) -> Dict:
        """Handle empty message input."""
        return {
            "response": "I missed that message. Could you send it one more time?",
            "intent": "general_query",
            "sentiment": "neutral",
            "conversation_state": self.conversation_state,
            "context": self.user_context
        }
    
    def get_user_mood(self) -> str:
        """Get the user's current mood from emotional memory."""
        try:
            return self.emotional_memory.get_current_mood(self.user_id)
        except Exception:
            return "neutral"
    
    def get_conversation_topics(self, limit: int = 10) -> List[str]:
        """Get the user's recent conversation topics."""
        try:
            return self.emotional_memory.get_conversation_topics(self.user_id, limit)
        except Exception:
            return []


def get_smart_chat_service(
    db: Session,
    user_id: UUID,
    use_mock: bool = False,
    conversation_id: Optional[UUID] = None
) -> SmartChatService:
    return SmartChatService(db=db, user_id=user_id, use_mock=use_mock, conversation_id=conversation_id)


__all__ = [
    "SmartChatService",
    "get_smart_chat_service"
]
