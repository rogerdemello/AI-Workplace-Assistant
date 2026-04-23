from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Enum as SQLEnum, Text, Date
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, date
import enum

from ..database import Base
from ..core.time import utcnow_naive


class LeaveStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class LeaveType(str, enum.Enum):
    paid = "paid"
    sick = "sick"
    work_from_home = "work_from_home"
    unpaid = "unpaid"


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False)
    leave_type = Column(SQLEnum(LeaveType), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    status = Column(SQLEnum(LeaveStatus), default=LeaveStatus.pending, index=True)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    user = relationship("User", foreign_keys=[user_id])
    manager = relationship("User", foreign_keys=[manager_id])