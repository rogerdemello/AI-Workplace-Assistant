from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class OnboardingChecklist(Base):
    __tablename__ = "onboarding_checklist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    task_name = Column(String(200), nullable=False)
    task_description = Column(String(1000))
    is_completed = Column(Boolean, default=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive)

    user = relationship("User", back_populates="onboarding_tasks")