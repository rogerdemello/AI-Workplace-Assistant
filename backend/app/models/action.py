from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from ..database import Base


class HRActionType(str, enum.Enum):
    schedule_checkin = "schedule_checkin"
    one_on_one = "1:1_meeting"
    wellness_check = "wellness_check"
    performance_review = "performance_review"
    follow_up = "follow_up"


class HRActionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    cancelled = "cancelled"


class HRAction(Base):
    __tablename__ = "hr_actions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    status = Column(SQLEnum(HRActionStatus), default=HRActionStatus.pending, index=True)
    scheduled_at = Column(DateTime, nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employee = relationship("User", foreign_keys=[employee_id])
    creator = relationship("User", foreign_keys=[created_by])