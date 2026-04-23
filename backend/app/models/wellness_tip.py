from sqlalchemy import Column, String, UUID, DateTime, Enum as SQLEnum, Text, Boolean
import uuid
from datetime import datetime
import enum

from ..database import Base
from ..core.time import utcnow_naive


class WellnessTipType(str, enum.Enum):
    stretch = "stretch"
    hydration = "hydration"
    eye_break = "eye_break"


class WellnessTip(Base):
    __tablename__ = "wellness_tips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tip_type = Column(SQLEnum(WellnessTipType), nullable=False, index=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    emoji = Column(String(10), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)