import json
import logging
from typing import Dict, List, Optional, Union
from datetime import datetime

from ..ai_client import get_ai_client, AzureOpenAIClient, MockAzureOpenAIClient
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
    }
}

INTENT_LIST = list(INTENTS.keys())

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

    def classify(self, message: str, user_id: Optional[str] = None) -> Dict:
        """Classify the user message into one of the predefined intents."""
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

            intent = result.get("intent", "general_query")
            confidence = float(result.get("confidence", 0.5))
            reasoning = result.get("reasoning", "")

            # Validate intent is in our list
            if intent not in INTENT_LIST:
                intent = "general_query"
                confidence = min(confidence, 0.5)

            classification_result = {
                "intent": intent,
                "confidence": confidence,
                "reasoning": reasoning
            }

            # Track history
            self._add_to_history(
                message=message,
                user_id=user_id,
                result=classification_result
            )

            return classification_result

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
