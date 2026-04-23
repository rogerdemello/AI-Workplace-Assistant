from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, String, Text, UUID, ForeignKey, UniqueConstraint

from ..database import Base
from ..core.time import utcnow_naive


class CalendarIntegration(Base):
    __tablename__ = "calendar_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)  # google | microsoft

    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String(32), nullable=False, default="Bearer")
    expires_at = Column(DateTime, nullable=True)
    connected_at = Column(DateTime, nullable=True)

    oauth_state_hash = Column(String(128), nullable=True)
    oauth_state_expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_calendar_integrations_user_provider"),
    )
