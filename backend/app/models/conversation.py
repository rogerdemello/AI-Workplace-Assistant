from sqlalchemy import Boolean, Column, String, UUID, ForeignKey, DateTime, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from ..database import Base
from ..core.time import utcnow_naive

class ConversationStatus(str, enum.Enum):
    active = "active"
    closed = "closed"

class MessageSender(str, enum.Enum):
    user = "user"
    bot = "bot"
    hr_agent = "hr_agent"
    system = "system"

class SentimentLabel(str, enum.Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    status = Column(SQLEnum(ConversationStatus), default=ConversationStatus.active, index=True)
    started_at = Column(DateTime, default=utcnow_naive, index=True)
    ended_at = Column(DateTime, nullable=True)

    # Flow state for conversation persistence
    active_flow = Column(String(100), nullable=True, index=True)
    last_intent = Column(String(100), nullable=True, index=True)
    flow_data = Column(Text, nullable=True)
    state = Column(JSONB, nullable=True)
    last_question = Column(String(255), nullable=True)
    completed = Column(Boolean, default=False)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True)
    sender = Column(SQLEnum(MessageSender), nullable=False)
    message_text = Column(Text, nullable=False)
    intent = Column(String(100), nullable=True, index=True)
    sentiment = Column(SQLEnum(SentimentLabel), nullable=True)
    confidence = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)

    conversation = relationship("Conversation", back_populates="messages")
