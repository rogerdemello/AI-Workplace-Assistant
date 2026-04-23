from sqlalchemy import Column, UUID, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class AppreciationNote(Base):
    __tablename__ = "appreciation_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    is_anonymous = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)

    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])