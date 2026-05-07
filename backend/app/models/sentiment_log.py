from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UUID
import uuid

from ..core.time import utcnow_naive
from ..database import Base


class SentimentLog(Base):
    __tablename__ = "sentiment_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True, index=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False, index=True)
    score = Column(Integer, nullable=False, index=True)  # normalized 0-100
    label = Column(String(20), nullable=False, index=True)  # positive|neutral|negative
    emotion = Column(String(50), nullable=False, default="neutral")
    # llm | lexicon | hybrid | provided (upstream label from chat routing)
    analysis_source = Column(String(16), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
