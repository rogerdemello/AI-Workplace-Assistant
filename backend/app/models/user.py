from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from ..database import Base
from ..core.time import utcnow_naive


class UserRole(str, enum.Enum):
    employee = "employee"
    manager = "manager"
    hr = "hr"
    admin = "admin"


class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.employee)
    department_id = Column(UUID, ForeignKey("departments.id"), nullable=True)
    designation = Column(String(100))
    manager_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    status = Column(SQLEnum(UserStatus), default=UserStatus.active, index=True)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    memory = relationship("ConversationMemory", back_populates="user")
    onboarding_tasks = relationship("OnboardingChecklist", back_populates="user")
    onboarding_assignments = relationship("OnboardingBuddy", foreign_keys="OnboardingBuddy.user_id", back_populates="user")
    onboarding_buddy_roles = relationship("OnboardingBuddy", foreign_keys="OnboardingBuddy.buddy_id", back_populates="buddy")
