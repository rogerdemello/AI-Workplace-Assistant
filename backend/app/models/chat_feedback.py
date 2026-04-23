from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class ChatFeedback(Base):
    __tablename__ = "chat_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True)
    rating = Column(Integer, nullable=False, index=True)
    comment = Column(Text, nullable=True)
    intent = Column(String(100), nullable=True, index=True)
    sentiment = Column(String(32), nullable=True, index=True)
    source = Column(String(32), nullable=False, default="chat", index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)

    user = relationship("User")
    conversation = relationship("Conversation")
