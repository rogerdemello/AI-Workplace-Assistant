from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class OnboardingBuddy(Base):
    __tablename__ = "onboarding_buddies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    buddy_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    assigned_at = Column(DateTime, default=utcnow_naive)
    active_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    assigned_by = Column(UUID, ForeignKey("users.id"), nullable=True)
    notes = Column(String(1000))

    user = relationship("User", foreign_keys=[user_id], back_populates="onboarding_assignments")
    buddy = relationship("User", foreign_keys=[buddy_id], back_populates="onboarding_buddy_roles")