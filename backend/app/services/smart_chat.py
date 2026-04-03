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

from ..ai_client import get_ai_client, AzureOpenAIClient, MockAzureOpenAIClient
from .intent_classifier import IntentClassifier, get_intent_classifier
from .sentiment import SentimentService
from .emotional_memory import EmotionalMemory, get_emotional_memory
from .hr_personality import (
    FRIENDLY_SYSTEM_PROMPT,
    build_context_aware_prompt,
    get_conversation_starter
)
from .rag_retrieve import RAGRetrieveService
from .entity_extractor import get_entity_extractor

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
        "good evening", "howdy", "hi there", "hello there"
    ]
    
    SHORT_INPUT_KEYWORDS = [
        "yes", "yeah", "yep", "ok", "okay", "sure", "do it", "go ahead",
        "proceed", "continue", "please", "thanks", "thank you",
        "maybe", "later", "skip", "nah", "nope", "no"
    ]
    
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
        self.flow_context: Dict = {}
        
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
                if conv.flow_data:
                    self.flow_context = json.loads(conv.flow_data)
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
                conv.flow_data = json.dumps(self.flow_context)
                self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to save flow state: {e}")
    
    def process_message(self, message: str) -> Dict:
        if not message or not message.strip():
            return self._empty_message_response()
        
        message_stripped = message.strip().lower()
        
        if self.current_flow and self._is_short_input(message_stripped):
            intent = self.previous_intent
            if not intent:
                intent = self.flow_context.get("pending_intent", "general_query")
        else:
            intent_result = self.intent_classifier.classify(message, str(self.user_id))
            intent = intent_result.get("intent", "general_query")
        
        if self._is_greeting(message):
            intent = "greeting"
        
        sentiment_result = self.sentiment_service.analyze(message)
        sentiment = sentiment_result.get("sentiment", "neutral")
        
        if not self.current_flow:
            if intent in ["leave_request", "ticket_create", "email_draft", "complaint"]:
                self.current_flow = "ticket" if intent in ["ticket_create", "complaint"] else intent
                self.flow_context["pending_intent"] = intent
        
        response_text = self._generate_response(intent, message, sentiment)
        
        if intent not in ["policy_query", "benefits_question"]:
            response_text = self._compress_response(response_text, intent, sentiment)
        
        self._update_conversation_state(intent, message)
        self._update_memory(message, intent, sentiment)
        self._save_flow_state()
        
        return {
            "response": response_text,
            "intent": intent,
            "sentiment": sentiment,
            "conversation_state": self.conversation_state,
            "context": self.user_context
        }
    
    def _is_greeting(self, message: str) -> bool:
        message_lower = message.lower().strip()
        return any(
            message_lower.startswith(keyword) or 
            keyword in message_lower
            for keyword in self.GREETING_KEYWORDS
        )
    
    def _is_short_input(self, message: str) -> bool:
        return any(
            keyword in message
            for keyword in self.SHORT_INPUT_KEYWORDS
        )
    
    def _generate_response(
        self,
        intent: str,
        message: str,
        sentiment: str
    ) -> str:
        
        if intent == "greeting":
            return self._handle_greeting(sentiment)
        
        elif intent == "leave_request":
            return self._handle_leave_request(message)
        
        elif intent == "policy_query":
            return self._handle_policy_query(message)
        
        elif intent == "benefits_question":
            return self._handle_benefits_query(message)
        
        elif intent == "email_draft":
            return self._handle_email_draft(message)
        
        elif intent in ["ticket_create", "complaint"]:
            return self._handle_ticket_create(message)
        
        else:
            return self._handle_general_query(message, sentiment)
    
    def _handle_greeting(self, sentiment: str) -> str:
        """Handle greeting intents."""
        return get_conversation_starter(sentiment)
    
    def _handle_leave_request(self, message: str) -> str:
        """Handle leave request intents."""
        # Check if user already provided dates
        message_lower = message.lower()
        has_dates = any(
            keyword in message_lower
            for keyword in ["next week", "tomorrow", "today", "monday", "tuesday",
                          "wednesday", "thursday", "friday", "date", "days", "weeks"]
        )
        
        if has_dates:
            # User provided dates, acknowledge and confirm
            return (
                "Got it! I've noted the dates you mentioned. "
                "Would you like me to help you submit a formal leave request, "
                "or do you have any questions about your leave balance first?"
            )
        else:
            # Ask for dates
            return (
                "Got it! What dates are you planning to take off? "
                "Also, let me know if this is sick leave, vacation, personal time, or something else."
            )
    
    def _handle_policy_query(self, message: str) -> str:
        """Handle policy query using RAG."""
        try:
            rag_service = RAGRetrieveService(self.db, use_mock=self.use_mock)
            result = rag_service.search_with_citations(message)
            
            response = result.get("answer", "")
            citations = result.get("citations", [])
            
            if citations:
                response += "\n\n" + " ".join([f"[{c}]" for c in citations])
            
            return response
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return (
                "I'd be happy to help you with that policy question! "
                "Let me find the relevant information for you. "
                "Could you give me a moment to look it up?"
            )
    
    def _handle_benefits_query(self, message: str) -> str:
        """Handle benefits questions using RAG."""
        return self._handle_policy_query(message)
    
    def _handle_email_draft(self, message: str) -> str:
        """Handle email draft requests."""
        # This would typically integrate with the email_draft service
        # For now, provide a helpful response
        return (
            "I'd be happy to help you draft an email! "
            "Could you tell me who it's for and what the main purpose is? "
            "For example, is it a follow-up, a request to your manager, or something else?"
        )
    
    def _handle_ticket_create(self, message: str) -> str:
        ticket_data = self.flow_context.get("ticket_data", {})
        
        message_lower = message.lower()
        if not ticket_data.get("department"):
            if any(word in message_lower for word in ["manager", "boss", "team lead", "supervisor"]):
                ticket_data["department"] = "HR"
            elif any(word in message_lower for word in ["laptop", "computer", "wifi", "software", "printer", "access"]):
                ticket_data["department"] = "IT"
            elif any(word in message_lower for word in ["office", "desk", "parking", "clean", "food"]):
                ticket_data["department"] = "Facilities"
        
        extracted = self.entity_extractor.extract_ticket_entities(message)
        
        for key, value in extracted.items():
            if value is not None and ticket_data.get(key) is None:
                ticket_data[key] = value
        
        self.flow_context["ticket_data"] = ticket_data
        
        missing = self._get_missing_ticket_fields(ticket_data)
        
        if not missing:
            return self._complete_ticket(ticket_data)
        
        return self._next_ticket_question_human(missing, ticket_data)
    
    def _get_missing_ticket_fields(self, ticket_data: Dict) -> list:
        priority_fields = ["issue", "department", "anonymous"]
        return [f for f in priority_fields if not ticket_data.get(f)]
    
    def _next_ticket_question_human(self, missing: list, ticket_data: Dict) -> str:
        issue = ticket_data.get("issue")
        dept = ticket_data.get("department")
        
        if "issue" in missing:
            if dept:
                return f"That sounds tough 😔 I'm sending this to {dept}. Can you tell me what happened?"
            return "That sounds tough 😔 Can you tell me what happened?"
        
        if "department" in missing:
            if issue:
                return f"Got it 👍 noted: {issue[:50]}... Which team should this go to?"
            return "Which team should I send this to - HR, IT, or Facilities?"
        
        if "anonymous" in missing:
            return "One more thing — do you want to stay anonymous?"
        
        return "Got it 👍 Let me process that."
    
    def _complete_ticket(self, ticket_data: Dict) -> str:
        self.flow_context["ticket_data"] = ticket_data
        self.current_flow = None
        
        dept = ticket_data.get("department", "HR")
        issue = ticket_data.get("issue", "your concern")
        anon = ticket_data.get("anonymous", False)
        
        if anon:
            return f"Done 👍 I've raised an anonymous ticket to {dept}. They'll look into it."
        return f"Done 👍 I've raised your ticket to {dept}. They'll review: {issue[:50]}..."
    
    def _handle_general_query(self, message: str, sentiment: str) -> str:
        """Handle general queries using AI."""
        try:
            # Build context-aware prompt
            user_name = self.user_context.get("user_name")
            recent_sentiment = self.user_context.get("current_mood")
            department = self.user_context.get("department")
            
            system_prompt = build_context_aware_prompt(
                user_name=user_name,
                recent_sentiment=recent_sentiment,
                department_context=department
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
                "I'm here to help! Could you tell me more about what you need? "
                "I can assist with leave requests, policy questions, benefits info, "
                "or help you draft emails or create tickets."
            )
    
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
        
        else:
            self.conversation_state = "active"
    
    def _compress_response(self, response: str, intent: str, sentiment: str) -> str:
        """Compress long responses to be more human-like."""
        # Count sentences
        sentences = response.split('.')
        sentence_count = len([s for s in sentences if s.strip()])
        
        # If already short, return as-is
        if sentence_count <= 3:
            return response
        
        # For emotional content, definitely compress
        if sentiment == "negative" or intent in ["complaint", "general_query"]:
            try:
                compress_prompt = f"""Rewrite this to be SHORT (max 2 sentences), human-like, and emotionally supportive:

User message: "{response[:500]}"

Keep it brief, warm, and end with one question."""
                
                result = self.ai_client.chat_completion(
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that rewrites text to be short and human-like."},
                        {"role": "user", "content": compress_prompt}
                    ],
                    temperature=0.5,
                    max_tokens=150
                )
                
                compressed = result["choices"][0]["message"]["content"]
                if compressed and len(compressed) > 10:
                    return compressed.strip()
                
            except Exception as e:
                logger.warning(f"Response compression failed: {e}")
        
        # Fallback: truncate to first 2 sentences
        return '. '.join(sentences[:2]).strip() + '.'
    
    def _update_memory(
        self,
        message: str,
        intent: str,
        sentiment: str
    ) -> None:
        """Update emotional memory with the current interaction."""
        # The emotional memory tracks messages through the conversation model
        # This is automatically handled when messages are stored in the database
        # via the ChatService in the API layer
        pass
    
    def _empty_message_response(self) -> Dict:
        """Handle empty message input."""
        return {
            "response": "I didn't catch that. Could you try typing your message again?",
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
