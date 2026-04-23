from sqlalchemy import Column, String, UUID, DateTime
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class Department(Base):
    __tablename__ = "departments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    created_at = Column(DateTime, default=utcnow_naive)
