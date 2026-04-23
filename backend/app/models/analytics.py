from datetime import datetime
from sqlalchemy import Column, String, Text, Float, Integer, Boolean, Date, DateTime, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
from app.core.time import utcnow_naive
import uuid


class MentalHealthScore(Base):
    __tablename__ = "mental_health_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, nullable=False)
    factors = Column(JSONB, default={})
    trend = Column(String(20), default="stable")
    created_at = Column(DateTime(timezone=True), default=utcnow_naive)
    created_at_date = Column(Date, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "created_at_date", name="uq_mental_health_score_user_date"),
    )


class BurnoutPrediction(Base):
    __tablename__ = "burnout_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(20), default="low")
    factors = Column(JSONB, default={})
    confidence = Column(Float)
    predicted_at = Column(DateTime(timezone=True), default=utcnow_naive)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow_naive)

    __table_args__ = (
        Index("idx_burnout_predictions_user_date", "user_id", "predicted_at"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="ck_burnout_score_range"),
    )


class SentimentHistory(Base):
    __tablename__ = "sentiment_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(50), nullable=False)
    sentiment = Column(String(20), nullable=False)
    score = Column(Float, nullable=False)
    context = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=utcnow_naive)

    __table_args__ = (
        Index("idx_sentiment_history_user_date", "user_id", "created_at"),
    )


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_date = Column(Date, unique=True, nullable=False)
    total_users = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    engagement_score = Column(Float)
    enps = Column(Float)
    avg_sentiment = Column(Float)
    open_tickets = Column(Integer, default=0)
    resolved_tickets = Column(Integer, default=0)
    avg_response_time_minutes = Column(Float)
    burnout_high_risk_count = Column(Integer, default=0)
    attrition_high_risk_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow_naive)


class Insight(Base):
    __tablename__ = "insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    insight_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), default="info")
    affected_entity_type = Column(String(50))
    affected_entity_id = Column(UUID(as_uuid=True))
    metrics = Column(JSONB)
    recommendations = Column(JSONB)
    is_resolved = Column(Boolean, default=False)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow_naive)
    updated_at = Column(DateTime(timezone=True), default=utcnow_naive, onupdate=utcnow_naive)


class ResponseSuggestion(Base):
    __tablename__ = "response_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_context = Column(Text, nullable=False)
    suggested_response = Column(Text, nullable=False)
    quality_score = Column(Float)
    usage_count = Column(Integer, default=0)
    is_approved = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=utcnow_naive)
    updated_at = Column(DateTime(timezone=True), default=utcnow_naive, onupdate=utcnow_naive)