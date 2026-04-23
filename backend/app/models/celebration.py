from sqlalchemy import Column, UUID, ForeignKey, DateTime, Enum as SQLEnum, Integer, Date
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from ..database import Base
from ..core.time import utcnow_naive


class CelebrationType(str, enum.Enum):
    work_anniversary = "work_anniversary"
    birthday = "birthday"
    milestone = "milestone"


class Celebration(Base):
    __tablename__ = "celebrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    celebration_type = Column(SQLEnum(CelebrationType), nullable=False, index=True)
    celebration_date = Column(Date, nullable=False, index=True)
    years_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)

    user = relationship("User", foreign_keys=[user_id])