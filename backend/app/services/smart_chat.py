"""
SmartChatService - Core conversation AI service for the Friendly HR assistant.

This service orchestrates:
- Intent classification
- Sentiment analysis
- Context-aware response generation
- Emotional memory tracking
- RAG-based policy queries
"""

from typing import Dict, Optional, List
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
    
    # EAP resources for employee wellness support
    EAP_RESOURCES = {
        "hotline": "1-800-XXX-XXXX",
        "website": "https://yourcompany.eap.com",
        "confidential_note": "All EAP consultations are confidential. Your manager will not be notified.",
    }
    
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
        "how much leave": "leave_balance",
        "remaining leave": "leave_balance",
        "leave days left": "leave_balance",
        # Reminder / alarm
        "set alarm": "reminder",
        "set a reminder": "reminder",
        "set reminder": "reminder",
        "remind me": "reminder",
        "create reminder": "reminder",
        "schedule reminder": "reminder",
        "add reminder": "reminder",
        "help": "help_request",
        "help me": "help_request",
        "i need help": "help_request",
        "can you help": "help_request",
        "assist me": "help_request",
        # Policy / benefits
        "policy": "policy_query",
        "handbook": "policy_query",
        "benefits": "benefits_question",
        # Escalation
        "escalate": "escalate_ticket",
        "escalation": "escalate_ticket",
        "urgent": "escalate_ticket",
        "supervisor": "escalate_ticket",
        "higher up": "escalate_ticket",
        "stressed": "emotional",
        "overwhelmed": "emotional",
        "anxious": "emotional",
        "depressed": "emotional",
        "burned out": "emotional",
        "i feel": "emotional",
        "mental health": "emotional",
        "can't cope": "emotional",
        "exhausted emotionally": "emotional",
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
            from ..models.conversation import Conversation
            conv = self.db.query(Conversation).filter(
                Conversation.id == self.conversation_id
            ).first()
            if conv:
                conv.active_flow = self.current_flow
                conv.last_intent = self.previous_intent
                conv.state = dict(self.flow_context) if self.flow_context else {}
                conv.last_question = self.flow_context.get("last_question")
                contract = self.flow_context.get("state_contract", {})
                conv.completed = bool(contract.get("completed", False))
                conv.flow_data = json.dumps(self.flow_context)
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

        if classified_intent in {"ticket_create", "complaint"}:
            if any(keyword in msg for keyword in self.LEAVE_BALANCE_KEYWORDS):
                return "leave_balance"
            if any(keyword in msg for keyword in ("set alarm", "set reminder", "remind me")):
                return "reminder"
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

    def _handle_help_request(self) -> str:
        return "Sure, I can help. What do you need assistance with?"

    def _handle_emotional(self, message: str, sentiment: str) -> str:
        from .mental_health import create_risk_alert

        response = (
            "I'm really sorry you're feeling this way. Your wellbeing matters, and I'm here to support you. "
            f"If you'd like, you can reach out to our EAP hotline ({self.EAP_RESOURCES['hotline']}) — it's completely confidential. "
            "Would you like me to share some wellbeing resources or suggest a quick check-in with someone from HR?"
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

        if (end - start).days + 1 > 60:
            return "Leave requests can't exceed 60 days. Could you adjust the dates?"

        overlap = self._check_leave_overlap(leave_data)
        if overlap:
            return (
                f"You already have leave from {overlap.start_date} to {overlap.end_date}. "
                "Do you still want to proceed?"
            )

        if start < _date.today():
            logger.info(f"Backdated leave request from user {self.user_id}: {start} to {end}")

        leave_type = self._normalize_leave_type(leave_data.get("leave_type"))
        days = (end - start).days + 1

        try:
            leave_request = LeaveRequest(
                user_id=self.user_id,
                start_date=start,
                end_date=end,
                leave_type=leave_type,
                reason=leave_data.get("reason"),
                status=LeaveStatus.pending,
            )
            self.db.add(leave_request)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error(f"Leave creation failed: {exc}")
            return "Something went wrong saving your leave request. Please try again."

        self._reset_flow()
        return (
            f"Done! {days}-day {leave_type.value.replace('_', ' ')} leave from "
            f"{start} to {end} submitted. Your manager will review it soon. 🗓️"
        )
    
    def _handle_policy_query(self, message: str) -> str:
        """Handle policy query using RAG."""
        if not get_feature_flags().enable_rag:
            return "Policy search is currently disabled by configuration."

        try:
            result = RAGOrchestrator(self.db, use_mock=self.use_mock).ask(message)
            
            response = result.get("answer", "")
            citations = result.get("citations", [])
            
            if citations:
                response += "\n\n" + " ".join([f"[{c}]" for c in citations])
            
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
        # This would typically integrate with the email_draft service
        # For now, provide a helpful response
        return (
            "I can draft that for you. "
            "Who is the email for?"
        )

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

        if "keep it anonymous" in normalized or "stay anonymous" in normalized:
            return True
        if "not anonymous" in normalized or "do not keep anonymous" in normalized:
            return False

        return None

    def _looks_like_ticket_issue(self, message: str) -> bool:
        text = message.strip()
        if len(text) >= 28:
            return True
        return bool(re.search(r"manager|harass|issue|problem|unfair|frustrat|payroll|policy|ticket|complaint", text, re.IGNORECASE))

    def _complete_ticket(self, ticket_data: Dict) -> str:
        # Ensure anonymous defaults to False if not set
        if ticket_data.get("anonymous") is None:
            ticket_data["anonymous"] = False

        dept = ticket_data.get("department", "HR")
        issue = ticket_data.get("issue", "your concern")
        details = ticket_data.get("details")
        against = ticket_data.get("against")
        severity = str(ticket_data.get("severity") or "mild").strip().lower()
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
        )

        if not is_new:
            self._reset_flow()
            ref = str(ticket.id)[:8]
            return (
                f"It looks like you already have a ticket for this (#{ref}). "
                f"I've skipped creating a duplicate. Want me to add a follow-up comment there?"
            )

        ticket_ref = str(ticket.id)[:8]
        self.flow_context["last_ticket_id"] = str(ticket.id)

        # Reset flow state cleanly
        self._reset_flow()

        if anon:
            return (
                f"Done. Your anonymous ticket has been raised with {dept}. 🎫\n"
                f"Reference: #{ticket_ref}. I'll check back if it stays unresolved."
            )
        return (
            f"Done. Your ticket is with {dept}. 🎫\n"
            f"Reference: #{ticket_ref}. I'll follow up if nothing happens."
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
            
            response = self.ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            return response["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            return (
                "I am here for you. "
                "What do you want to get done right now?"
            )

    def _deduplicate_response(self, response_text: str) -> str:
        text = (response_text or "").strip().lower()
        response_hash = hash(text)
        last_hash = self.flow_context.get("last_response_hash")
        if response_hash == last_hash and text:
            response_text = response_text + " Let me know if you need anything else."
        self.flow_context["last_response_hash"] = response_hash
        return response_text

    def _finalize_response(self, response: str, intent: str, sentiment: str, mode: str, message_count: int = 0) -> str:
        cleaned = " ".join((response or "").split())
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
            cleaned = self._append_eap_offer(cleaned)

        if self.should_offer_wellness_tip(message_count):
            cleaned = f"{cleaned} {self.get_wellness_tip()}"

        return cleaned
    
    def _append_eap_offer(self, response: str) -> str:
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
