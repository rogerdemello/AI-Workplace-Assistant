import json
import logging
import re
import hashlib
import time
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime

from ..ai_client import get_ai_client, AzureOpenAIClient, MockAzureOpenAIClient
from ..config import settings
from ..core.time import utcnow_naive
from .hr_personality import FRIENDLY_SYSTEM_PROMPT, EMOTIONALLY_AWARE_PROMPT

logger = logging.getLogger(__name__)

INTENTS = {
    "leave_request": {
        "description": "User requests time off or leave",
        "examples": [
            "I need 3 days off next week",
            "Can I take a vacation?",
            "I want to apply for leave",
            "Need to take a personal day",
            "Can I have sick leave for tomorrow?",
            "I need to request annual leave",
            "Taking a mental health day"
        ]
    },
    "policy_query": {
        "description": "User asks about company policy",
        "examples": [
            "What's the remote work policy?",
            "How many sick days do I have?",
            "What are the working hours?",
            "Tell me about the dress code",
            "What is the overtime policy?",
            "Can you explain the expense policy?",
            "What are the PTO accrual rules?"
        ]
    },
    "benefits_question": {
        "description": "User asks about employee benefits",
        "examples": [
            "What health insurance options do I have?",
            "Tell me about the 401k plan",
            "What are the PTO benefits?",
            "Is there a gym membership?",
            "What dental coverage is available?",
            "Tell me about parental leave",
            "What is the employee stock purchase plan?"
        ]
    },
    "email_draft": {
        "description": "User wants to draft an email",
        "examples": [
            "Help me write an email to my manager",
            "Can you help me draft a leave request email?",
            "Write a follow-up email",
            "Draft a professional email",
            "Help me compose an email",
            "Write an email to HR",
            "Draft a resignation letter"
        ]
    },
    "ticket_create": {
        "description": "User wants to create a support ticket",
        "examples": [
            "I need to report an issue",
            "Create a ticket for IT support",
            "I have a complaint",
            "File a request",
            "I need to submit a help desk ticket",
            "Report a workplace incident",
            "Create a maintenance request"
        ]
    },
    "emotional": {
        "description": "User expresses emotional distress or mental health concerns",
        "examples": [
            "I feel stressed",
            "I am overwhelmed",
            "I feel anxious",
            "I feel depressed",
            "I am burned out",
            "I can't cope",
            "I am exhausted emotionally",
            "I need mental health support"
        ]
    },
    "general_query": {
        "description": "General conversation or question",
        "examples": [
            "Hello",
            "How are you?",
            "What can you help me with?",
            "Thanks",
            "Good morning",
            "Hi there",
            "Thank you for your help"
        ]
    },
    "help_request": {
        "description": "User wants topical help (timesheet, email drafting, policy clarification, recognition note)",
        "examples": [
            "Help me with my timesheet",
            "I need help with my email",
            "Can you help me with the policy?",
            "Assist me with a recognition note",
            "Help me with missing hours",
        ],
    },
    "escalate_ticket": {
        "description": "User wants to escalate an existing open ticket to critical priority",
        "examples": [
            "Escalate my ticket",
            "Please escalate the ticket",
            "Escalate this complaint",
        ],
    },
    "reminder": {
        "description": "User wants to set or cancel a reminder",
        "examples": [
            "Remind me to drink water at 4pm",
            "Set a reminder for my 1:1",
            "Remind me to take my medicine",
        ],
    },
    "resignation_support": {
        "description": "User is considering leaving the company (not a leave request)",
        "examples": [
            "I want to resign",
            "I'm thinking of leaving the company",
            "I want to quit my job",
        ],
    },
    "leave_balance": {
        "description": "User asks how much leave is remaining (query only)",
        "examples": [
            "How many leaves do I have left?",
            "What is my leave balance?",
            "Leave days remaining",
        ],
    },
    "appreciation": {
        "description": "User wants to send appreciation / kudos / a shout-out to a colleague",
        "examples": [
            "Thanks to Priya for closing the bug",
            "Shoutout to Arjun — saved my release",
            "Kudos to Ananya for the deck",
            "Big credit to John for picking up the on-call",
        ],
    },
}

INTENT_LIST = list(INTENTS.keys())

# Fast-path regex routes — checked before LLM (ordered: most specific first)
# Each tuple: (compiled_regex, intent, confidence, reasoning)
_FAST_ROUTES: List[Tuple[re.Pattern, str, float, str]] = []


def _build_fast_routes() -> List[Tuple[re.Pattern, str, float, str]]:
    """Compile heuristic intent routes for sub-millisecond classification."""
    routes: List[Tuple[str, str, float, str]] = [
        # Leave request (apply for leave)
        (r"\b(apply\s+(for\s+)?leave|request\s+(for\s+)?leave|book\s+leave|take\s+(a\s+)?day\s+off|take\s+time\s+off|need\s+\d+\s+days?\s+off|want\s+(a\s+)?vacation|going\s+on\s+vacation|need\s+a\s+personal\s+day|take\s+sick\s+leave|mental\s+health\s+day)\b", "leave_request", 0.92, "Fast-path: explicit leave request phrasing"),
        # Leave balance (query only)
        (r"\b(how\s+many\s+leaves?\s+((do\s+i\s+have|left|remaining|balance))|\bleave\s+balance\b|\bleaves?\s+left\b|\bremaining\s+leave\b|\bhow\s+much\s+leave\b|\bleave\s+days?\s+left\b)\b", "policy_query", 0.90, "Fast-path: leave balance inquiry"),
        # Ticket / complaint
        (r"\b(raise\s+a?\s+ticket|file\s+a?\s+complaint|report\s+(an?\s+)?issue|create\s+a?\s+ticket|submit\s+a?\s+ticket|complaint\s+about|problem\s+with\s+my|issue\s+with\s+my|something\s+is\s+broken|not\s+working)\b", "ticket_create", 0.92, "Fast-path: ticket or complaint phrasing"),
        # Policy
        (r"\b(what\s+(is|are)\s+(the\s+)?policy|handbook|company\s+rules?|remote\s+work\s+policy|wfh\s+policy|dress\s+code|overtime\s+policy|expense\s+policy|pto\s+(policy|rules?)|working\s+hours)\b", "policy_query", 0.90, "Fast-path: explicit policy query"),
        # Benefits
        (r"\b(health\s+insurance|dental\s+coverage|vision\s+insurance|401k|retirement\s+plan|stock\s+options|gym\s+membership|parental\s+leave|employee\s+benefits|what\s+benefits)\b", "benefits_question", 0.90, "Fast-path: benefits keyword"),
        # Email draft
        (r"\b(draft\s+(an?\s+)?email|write\s+(an?\s+)?email|help\s+me\s+compose|email\s+to\s+my|resignation\s+letter|follow[-\s]?up\s+email)\b", "email_draft", 0.91, "Fast-path: email drafting request"),
        # Emotional / distress
        (r"\b(i\s+feel\s+(stressed|anxious|depressed|overwhelmed|burned?\s+out|exhausted|hopeless|sad|empty)|i\s+can\'?t\s+cope|mental\s+health|i\s+need\s+therapy|panic\s+attack|want\s+to\s+quit|had\s+enough|not\s+okay|not\s+ok)\b", "emotional", 0.93, "Fast-path: emotional distress signal"),
        # Reminder — NOTE: not fast-pathed; _apply_intent_keyword_fallback handles it after LLM classify
        # Appreciation — MUST come before the bare "thanks" route below so
        # "thanks to <name>" doesn't get swallowed as a plain general "thanks".
        (r"\b(thanks?\s+to\s+[A-Za-z]|thank\s+you\s+to\s+[A-Za-z]|appreciat\w+\s+(?:goes\s+)?to\s+[A-Za-z]|appreciation\s+for\s+[A-Za-z]|shout[-\s]?out\s+to\s+[A-Za-z]|kudos\s+to\s+[A-Za-z]|credit\s+(?:goes\s+)?to\s+[A-Za-z]|hat\s+tip\s+to\s+[A-Za-z])", "appreciation", 0.92, "Fast-path: appreciation toward a person"),
        (r"\b[A-Z][a-zA-Z]{1,30}(?:\s+[A-Z][a-zA-Z]{1,30})?\s+(?:really\s+|absolutely\s+)?(?:helped|saved|covered|carried|crushed\s+it)\b", "appreciation", 0.85, "Fast-path: <Name> helped/saved me pattern"),
        # Greeting / thanks
        (r"^(hi|hello|hey|howdy|good\s+(morning|afternoon|evening)|what\s+can\s+you\s+do|who\s+are\s+you)([\s,]|$|\!|\?|\.)", "general_query", 0.88, "Fast-path: greeting or intro"),
        (r"^(thanks?|thank\s+you|thx|ty)(\s|$|\!|\.|\?)", "general_query", 0.88, "Fast-path: thanks"),
        # Help (specific topical help — timesheet, email, policy, complaint)
        (r"\b(help\s+me\s+with|i\s+need\s+help\s+with|assist\s+me\s+with|can\s+you\s+help\s+with)\b", "help_request", 0.88, "Fast-path: topical help request"),
        # Generic help (open-ended) — falls back to general query
        (r"\b(help\s+me|i\s+need\s+help|can\s+you\s+help|what\s+can\s+you\s+help\s+with)\b", "general_query", 0.85, "Fast-path: generic help"),
    ]
    compiled = []
    for pattern, intent, conf, reason in routes:
        try:
            compiled.append((re.compile(pattern, re.IGNORECASE), intent, conf, reason))
        except re.error as e:
            logger.warning(f"Invalid fast-route regex '{pattern}': {e}")
    return compiled


_FAST_ROUTES = _build_fast_routes()

# Intent history storage (in production, use a database)
_intent_history: List[Dict] = []


class IntentClassifier:
    def __init__(
        self,
        ai_client: Optional[Union[AzureOpenAIClient, MockAzureOpenAIClient]] = None,
        confidence_threshold: float = 0.7
    ):
        self.ai_client = ai_client or get_ai_client()
        self.confidence_threshold = confidence_threshold

    def _fast_classify(self, message: str) -> Optional[Dict]:
        """Sub-millisecond heuristic classifier for obvious intents."""
        if not message:
            return None
        for regex, intent, confidence, reasoning in _FAST_ROUTES:
            if regex.search(message):
                return {
                    "intent": intent,
                    "confidence": confidence,
                    "reasoning": reasoning,
                }
        return None

    @staticmethod
    def _cache_key(message: str) -> str:
        """Normalized cache key for intent classification."""
        normalized = message.strip().lower()[:200]
        h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        return f"intent_classify:{h}"

    def classify(self, message: str, user_id: Optional[str] = None) -> Dict:
        """Classify the user message into one of the predefined intents.

        Path:
        1. Fast heuristic router (regex) — sub-millisecond.
        2. Redis cache — avoids duplicate LLM calls within TTL.
        3. LLM fallback — Azure OpenAI with JSON mode.
        """
        start_ts = time.perf_counter()
        path = "fast"

        # 1. Fast heuristic
        fast_result = self._fast_classify(message)
        if fast_result:
            classification_result = fast_result
        else:
            # 2. Cache lookup
            cache_key = self._cache_key(message)
            try:
                from ..cache import get_cached, set_cached
                cached = get_cached(cache_key)
                if cached:
                    classification_result = cached
                    path = "cache"
                elif settings.FAST_CHAT_MODE:
                    # Latency mode: skip the LLM classify fallback (a full extra
                    # gpt-4o round-trip per turn). Explicit intents are caught by
                    # the regex routes above; everything else is general chat —
                    # the general handler still replies, and mid-flow this reads
                    # as "continue the current flow".
                    classification_result = {
                        "intent": "general_query",
                        "confidence": 0.4,
                        "reasoning": "fast-mode default (LLM classify skipped)",
                    }
                    path = "fast-default"
                else:
                    # 3. LLM fallback
                    classification_result = self._llm_classify(message)
                    path = "llm"
                    set_cached(cache_key, classification_result, ttl=60)
            except Exception:
                # Cache unavailable — fall through to LLM (unless fast mode)
                if settings.FAST_CHAT_MODE:
                    classification_result = {
                        "intent": "general_query",
                        "confidence": 0.4,
                        "reasoning": "fast-mode default (LLM classify skipped)",
                    }
                    path = "fast-default"
                else:
                    classification_result = self._llm_classify(message)
                    path = "llm"

        duration_ms = round((time.perf_counter() - start_ts) * 1000, 2)
        logger.info(
            "intent_classify",
            extra={
                "classify_path": path,
                "classify_duration_ms": duration_ms,
                "intent": classification_result.get("intent"),
                "confidence": classification_result.get("confidence"),
                "message_preview": (message or "")[:60],
            },
        )

        # Validate intent is in our list
        intent = classification_result.get("intent", "general_query")
        if intent not in INTENT_LIST:
            intent = "general_query"
            classification_result["confidence"] = min(classification_result.get("confidence", 0.5), 0.5)
            classification_result["intent"] = intent

        # Track history
        self._add_to_history(
            message=message,
            user_id=user_id,
            result=classification_result
        )

        return classification_result

    def _llm_classify(self, message: str) -> Dict:
        """LLM-based intent classification (original behavior)."""
        prompt = self._build_prompt(message)
        try:
            response = self.ai_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": f"""{FRIENDLY_SYSTEM_PROMPT}

You are also an intent classifier. Classify the user message into exactly one of these intents: {', '.join(INTENT_LIST)}.
Return ONLY valid JSON with no additional text: {{"intent": "intent_name", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}

Intent definitions:
{self._get_intent_definitions()}

Remember: Be friendly and empathetic in your reasoning."""
                    },
                    {"role": "user", "content": message}
                ],
                temperature=0.3,
                max_tokens=300
            )

            content = response["choices"][0]["message"]["content"]
            result = json.loads(content)

            return {
                "intent": result.get("intent", "general_query"),
                "confidence": float(result.get("confidence", 0.5)),
                "reasoning": result.get("reasoning", ""),
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse intent classification response: {e}")
            return {
                "intent": "general_query",
                "confidence": 0.3,
                "reasoning": "Failed to parse classification response"
            }
        except Exception as e:
            logger.error(f"Intent classification error: {str(e)}")
            return {
                "intent": "general_query",
                "confidence": 0.3,
                "reasoning": f"Classification error: {str(e)}"
            }

    def classify_with_fallback(
        self,
        message: str,
        user_id: Optional[str] = None
    ) -> Dict:
        """Classify intent with fallback handling for low confidence."""
        result = self.classify(message, user_id)

        if result["confidence"] < self.confidence_threshold:
            result["fallback"] = True
            result["suggestion"] = (
                "I want to make sure I understand you correctly. "
                "Could you rephrase your message or provide more details?"
            )
            result["escalate"] = result["confidence"] < 0.4
            if result["escalate"]:
                result["suggestion"] = (
                    "I'm having trouble understanding your request. "
                    "Would you like me to connect you with a human agent?"
                )
        else:
            result["fallback"] = False
            result["escalate"] = False

        return result

    def _build_prompt(self, message: str) -> str:
        examples_text = "\n".join([
            f"- {ex}" for intent_data in INTENTS.values()
            for ex in intent_data["examples"]
        ])
        return f"""Classify this message into one of these intents:
{', '.join(INTENT_LIST)}

Examples:
{examples_text}

Message: {message}

Respond with JSON: {{"intent": "intent_name", "confidence": 0.0-1.0, "reasoning": "explanation"}}"""

    def _get_intent_definitions(self) -> str:
        """Get formatted intent definitions for the system prompt."""
        definitions = []
        for intent_name, intent_data in INTENTS.items():
            examples = ", ".join(intent_data["examples"][:3])
            definitions.append(
                f"- {intent_name}: {intent_data['description']} "
                f"(e.g., {examples})"
            )
        return "\n".join(definitions)

    def _add_to_history(
        self,
        message: str,
        user_id: Optional[str],
        result: Dict
    ) -> None:
        """Add classification result to history tracking."""
        entry = {
            "timestamp": utcnow_naive().isoformat(),
            "message": message,
            "user_id": user_id,
            "intent": result["intent"],
            "confidence": result["confidence"],
            "reasoning": result.get("reasoning", "")
        }
        _intent_history.append(entry)

        # Keep only last 1000 entries
        if len(_intent_history) > 1000:
            _intent_history.pop(0)

    def get_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get intent classification history."""
        if user_id:
            return [
                entry for entry in _intent_history
                if entry.get("user_id") == user_id
            ][-limit:]
        return _intent_history[-limit:]


def get_intent_classifier(
    confidence_threshold: float = 0.7,
    use_mock: bool = False
) -> IntentClassifier:
    """Factory function to create IntentClassifier instance."""
    ai_client = get_ai_client(use_mock=use_mock)
    return IntentClassifier(
        ai_client=ai_client,
        confidence_threshold=confidence_threshold
    )


__all__ = [
    "IntentClassifier",
    "get_intent_classifier",
    "INTENTS",
    "INTENT_LIST"
]
