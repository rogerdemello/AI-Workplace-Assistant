from typing import Dict, List, Optional
from uuid import UUID
import logging
import re

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


SMART_RESPONSE_TEMPLATES = {
    "leave_request": [
        "I've submitted your leave request for {start_date} to {end_date}. Your manager will be notified for approval.",
        "Your leave request is being processed. You'll receive a confirmation once approved.",
        "I've created the leave request. Expected turnaround is 1-2 business days for manager approval.",
    ],
    "ticket_escalation": [
        "I've escalated your ticket to the HR team. You should hear back within 24 hours.",
        "Your concern has been escalated. A senior HR team member will reach out shortly.",
        "I've flagged this for immediate attention. Expect a response within 24 hours.",
    ],
    "policy_question": [
        "Based on company policy: {answer}. Would you like more details?",
        "Here's what our policy states: {answer}. Let me know if you need clarification.",
        "I found the relevant policy information for you. {answer}",
    ],
    "general_inquiry": [
        "I'd be happy to help with that. Let me check our HR resources.",
        "That's a great question. Let me look into the details for you.",
        "I understand you need information about this. Let me provide a comprehensive answer.",
    ],
    "wellbeing_check": [
        "I'm glad you reached out. Your wellbeing is important. Would you like to schedule a check-in?",
        "Thank you for sharing. I'm here to support you. What's on your mind?",
        "I appreciate you connecting with Mark. Let's discuss what's going on.",
    ],
    "appreciation": [
        "Your message has been shared! They'll be notified through our appreciation system.",
        "I've sent the appreciation note. Spreading positivity is what we need!",
        "Done! Your colleague will receive your thoughtful message.",
    ],
}


class SmartResponseSuggestionService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def _classify_intent(self, message: str) -> str:
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["leave", "vacation", "time off", "pto", "sick"]):
            return "leave_request"
        if any(word in message_lower for word in ["escalate", "urgent", "important", "complaint"]):
            return "ticket_escalation"
        if any(word in message_lower for word in ["policy", "rule", "guideline", "benefit"]):
            return "policy_question"
        if any(word in message_lower for word in ["thank", "appreciate", "great", "awesome"]):
            return "appreciation"
        if any(word in message_lower for word in ["burnout", "stress", "overwork", "tired", "mental"]):
            return "wellbeing_check"
        
        return "general_inquiry"

    def _extract_entities(self, message: str) -> Dict[str, str]:
        entities = {}
        
        date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|((jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2})'
        dates = re.findall(date_pattern, message.lower())
        if dates:
            entities["date"] = dates[0][0] if dates[0][0] else dates[0][1]
        
        return entities

    def suggest_response(
        self,
        user_message: str,
        context: Optional[Dict] = None,
    ) -> Dict:
        intent = self._classify_intent(user_message)
        entities = self._extract_entities(user_message)
        
        templates = SMART_RESPONSE_TEMPLATES.get(intent, SMART_RESPONSE_TEMPLATES["general_inquiry"])
        suggested = templates[0]
        
        if entities.get("date"):
            suggested = suggested.replace("{start_date}", entities.get("date", ""))
            suggested = suggested.replace("{end_date}", entities.get("date", ""))
        
        if context and context.get("last_policy"):
            suggested = suggested.replace("{answer}", context.get("last_policy", "")[:100])
        
        has_alternatives = len(templates) > 1
        
        return {
            "suggested_response": suggested,
            "matched_intent": intent,
            "confidence": 0.85 if intent != "general_inquiry" else 0.60,
            "alternatives": templates[1:3] if has_alternatives else [],
            "entities": entities,
        }

    def get_suggestions_for_conversation(
        self,
        conversation_id: UUID,
        limit: int = 5,
    ) -> List[Dict]:
        if not self.db:
            return []

        sql = text("""
            SELECT m.message_text, m.intent, m.created_at
            FROM messages m
            WHERE m.conversation_id = :conv_id
            ORDER BY m.created_at DESC
            LIMIT :limit
        """)

        result = self.db.execute(sql, {"conv_id": str(conversation_id), "limit": limit}).fetchall()

        suggestions = []
        for row in result:
            if row[1]:
                suggestions.append({
                    "intent": row[1],
                    "message": row[0][:100],
                    "timestamp": str(row[2]) if row[2] else None,
                })

        return suggestions

    def log_suggestion_usage(
        self,
        query_context: str,
        suggested_response: str,
        quality_score: Optional[float] = None,
    ) -> None:
        if not self.db:
            return

        try:
            sql = text("""
                INSERT INTO response_suggestions (query_context, suggested_response, quality_score)
                VALUES (:context, :response, :score)
            """)
            self.db.execute(sql, {
                "context": query_context[:500],
                "response": suggested_response[:2000],
                "score": quality_score,
            })
            self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to log response suggestion: {e}")
            self.db.rollback()


class ConversationSummarizationService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def summarize_conversation(
        self,
        conversation_id: UUID,
    ) -> Dict:
        if not self.db:
            return {
                "summary": "Conversation summary unavailable",
                "action_items": [],
                "priority": "normal",
            }

        sql = text("""
            SELECT 
                m.message_text,
                m.sender,
                m.intent,
                m.sentiment,
                m.created_at
            FROM messages m
            WHERE m.conversation_id = :conv_id
            ORDER BY m.created_at ASC
        """)

        messages = self.db.execute(sql, {"conv_id": str(conversation_id)}).fetchall()

        if not messages:
            return {
                "summary": "No messages in conversation",
                "action_items": [],
                "priority": "normal",
            }

        user_messages = []
        bot_messages = []
        intents = []
        sentiments = []

        for msg in messages:
            if msg[1] == "user":
                user_messages.append(msg[0])
            else:
                bot_messages.append(msg[0])
            
            if msg[2]:
                intents.append(msg[2])
            if msg[3]:
                sentiments.append(msg[3])

        summary_parts = []
        
        if len(user_messages) > 3:
            summary_parts.append(f"User engaged in {len(user_messages)} messages")
        else:
            summary_parts.append(f"User engaged in {len(user_messages)} message(s)")
        
        if intents:
            unique_intents = list(set(intents))
            summary_parts.append(f"Topics: {', '.join(unique_intents[:3])}")

        action_items = []
        for intent in intents:
            if intent in ["leave_request", "ticket_escalation", "escalate"]:
                action_items.append({
                    "type": "approval_pending",
                    "description": "Pending action required from HR/manager",
                })

        priority = "normal"
        if sentiments and "negative" in sentiments:
            priority = "high"

        summary = ". ".join(summary_parts) if summary_parts else "Standard HR conversation"

        return {
            "summary": summary,
            "message_count": len(messages),
            "action_items": action_items,
            "priority": priority,
            "duration_minutes": self._calculate_duration(messages),
        }

    def _calculate_duration(self, messages: List) -> int:
        if len(messages) < 2:
            return 0
        
        first_time = messages[0][4]
        last_time = messages[-1][4]
        
        if first_time and last_time:
            delta = last_time - first_time
            return int(delta.total_seconds() / 60)
        
        return 0

    def extract_action_items(
        self,
        conversation_id: UUID,
    ) -> List[Dict]:
        summary = self.summarize_conversation(conversation_id)
        return summary.get("action_items", [])


def get_response_suggestion_service(db: Optional[Session] = None) -> SmartResponseSuggestionService:
    return SmartResponseSuggestionService(db=db)


def get_summarization_service(db: Optional[Session] = None) -> ConversationSummarizationService:
    return ConversationSummarizationService(db=db)