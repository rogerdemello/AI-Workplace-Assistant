from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum

class ConversationStatus(str, Enum):
    active = "active"
    closed = "closed"

class MessageSender(str, Enum):
    user = "user"
    bot = "bot"
    hr_agent = "hr_agent"
    system = "system"

class SentimentLabel(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"

class MessageCreate(BaseModel):
    message_text: str
    sender: MessageSender = MessageSender.user

class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    sender: MessageSender
    message_text: str
    intent: Optional[str] = None
    sentiment: Optional[SentimentLabel] = None
    confidence: Optional[float] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ConversationCreate(BaseModel):
    pass

class ConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: ConversationStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    messages: List[MessageResponse] = []
    active_flow: Optional[str] = None
    last_intent: Optional[str] = None
    state: Optional[dict] = None
    last_question: Optional[str] = None
    completed: bool = False

    model_config = ConfigDict(from_attributes=True)

class ConversationListResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: ConversationStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    last_message: Optional[str] = None
    active_flow: Optional[str] = None
    last_intent: Optional[str] = None
    state: Optional[dict] = None
    last_question: Optional[str] = None
    completed: bool = False

    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None


class FlowMetadata(BaseModel):
    flow_name: Optional[str] = None
    intent: Optional[str] = None
    step: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    collected_fields: List[str] = Field(default_factory=list)
    completed: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "flow_name": "leave_request",
                "intent": "leave_request",
                "step": "reason",
                "missing_fields": ["reason"],
                "collected_fields": ["leave_type", "start_date", "end_date"],
                "completed": False,
            }
        }
    )


class ChatResponse(BaseModel):
    response: str
    intent: Optional[str] = None
    sentiment: Optional[SentimentLabel] = None
    conversation_state: Optional[dict] = None
    context: Optional[dict] = None
    flow_metadata: Optional[FlowMetadata] = None
    active_flow: Optional[str] = None
    last_intent: Optional[str] = None
    completed: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "response": "Noted 2026-05-02. And what is the last day?",
                "intent": "leave_request",
                "sentiment": "neutral",
                "conversation_state": {"state": "collecting_leave_details"},
                "context": {
                    "conversation_mode": "action",
                    "active_flow": "leave_request",
                },
                "flow_metadata": {
                    "flow_name": "leave_request",
                    "intent": "leave_request",
                    "step": "end_date",
                    "missing_fields": ["end_date", "reason"],
                    "collected_fields": ["leave_type", "start_date"],
                    "completed": False,
                },
                "active_flow": "leave_request",
                "last_intent": "leave_request",
                "completed": False,
            }
        }
    )


class ConversationStartResponse(BaseModel):
    conversation_id: UUID
    greeting: str


__all__ = [
    "ConversationStatus",
    "MessageSender",
    "SentimentLabel",
    "MessageCreate",
    "MessageResponse",
    "ConversationCreate",
    "ConversationResponse",
    "ConversationListResponse",
    "ChatRequest",
    "FlowMetadata",
    "ChatResponse",
    "ConversationStartResponse",
]
