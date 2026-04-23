from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    preferences = Column(JSON, nullable=True)
    last_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    user = relationship("User", back_populates="profile")