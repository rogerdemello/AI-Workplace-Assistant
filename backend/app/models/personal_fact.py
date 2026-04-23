from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Enum as SQLEnum, Text, Date
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from ..database import Base
from ..core.time import utcnow_naive


class PersonalFactType(str, enum.Enum):
    birthday = "birthday"
    work_anniversary = "work_anniversary"
    hobby = "hobby"
    family_note = "family_note"
    custom = "custom"


class PersonalFact(Base):
    __tablename__ = "personal_facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    fact_type = Column(SQLEnum(PersonalFactType), nullable=False, index=True)
    fact_value = Column(Text, nullable=False)
    source_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    user = relationship("User", foreign_keys=[user_id])