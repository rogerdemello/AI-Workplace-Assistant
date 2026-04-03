from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from ..database import Base


class Survey(Base):
    __tablename__ = "surveys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    questions = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True)
    allow_anonymous = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    creator = relationship("User", foreign_keys=[created_by])
    responses = relationship("SurveyResponse", back_populates="survey", cascade="all, delete-orphan")


class SurveyResponse(Base):
    __tablename__ = "survey_responses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    survey_id = Column(UUID(as_uuid=True), ForeignKey("surveys.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responses = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    survey = relationship("Survey", back_populates="responses")
    user = relationship("User", foreign_keys=[user_id])
