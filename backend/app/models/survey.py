from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class Survey(Base):
    __tablename__ = "surveys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    questions = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True)
    allow_anonymous = Column(Boolean, default=False)
    # Optional lifecycle tag so nudges can target the right survey
    # (e.g. "onboarding", "exit", "pulse"). Null = a generic ad-hoc survey.
    survey_type = Column(String(32), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=utcnow_naive)
    
    creator = relationship("User", foreign_keys=[created_by])
    responses = relationship("SurveyResponse", back_populates="survey", cascade="all, delete-orphan")


class SurveyResponse(Base):
    __tablename__ = "survey_responses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    survey_id = Column(UUID(as_uuid=True), ForeignKey("surveys.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responses = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utcnow_naive)
    
    survey = relationship("Survey", back_populates="responses")
    user = relationship("User", foreign_keys=[user_id])
