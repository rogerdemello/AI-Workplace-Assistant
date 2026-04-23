from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class ConversationMemory(Base):
    __tablename__ = "conversation_memory"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    tags = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    
    user = relationship("User", back_populates="memory")