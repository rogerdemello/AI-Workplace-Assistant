from sqlalchemy import Column, UUID, ForeignKey, Date, DateTime, JSON, Float, UniqueConstraint
import uuid
from datetime import datetime

from ..database import Base
from ..core.time import utcnow_naive


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "period_start", "period_end", name="uq_risk_snapshot_user_period"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    engagement_score = Column(Float, nullable=True)
    mood_score = Column(Float, nullable=True)
    burnout_risk = Column(Float, nullable=True)
    attrition_risk = Column(Float, nullable=True, index=True)
    silence_risk = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    risk_reasons = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
