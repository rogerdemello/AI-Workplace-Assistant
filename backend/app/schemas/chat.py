from pydantic import BaseModel, ConfigDict
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


class ChatResponse(BaseModel):
    response: str
    intent: Optional[str] = None
    sentiment: Optional[SentimentLabel] = None
    conversation_state: Optional[dict] = None
    context: Optional[dict] = None
    active_flow: Optional[str] = None
    last_intent: Optional[str] = None
    completed: bool = False


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
    "ChatResponse",
    "ConversationStartResponse",
]
