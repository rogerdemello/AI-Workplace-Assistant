from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Enum as SQLEnum, Integer
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from ..database import Base
from ..core.time import utcnow_naive


class AttachmentEntityType(str, enum.Enum):
    ticket = "ticket"
    leave_request = "leave_request"


class Attachment(Base):
    __tablename__ = "attachments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=False)
    entity_type = Column(SQLEnum(AttachmentEntityType), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
    
    user = relationship("User")