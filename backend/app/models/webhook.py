from datetime import datetime
import uuid
import enum

from sqlalchemy import Column, DateTime, String, Text, Boolean, Integer, UUID, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from ..database import Base
from ..core.time import utcnow_naive


class WebhookEventType(str, enum.Enum):
    """Event types that can trigger webhooks."""
    MOOD_LOGGED = "mood_logged"
    MOOD_TREND_ALERT = "mood_trend_alert"
    APPRECIATION_SENT = "appreciation_sent"
    APPRECIATION_RECEIVED = "appreciation_received"
    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    TICKET_RESOLVED = "ticket_resolved"
    LEAVE_REQUESTED = "leave_requested"
    LEAVE_APPROVED = "leave_approved"
    LEAVE_REJECTED = "leave_rejected"
    BIRTHDAY = "birthday"
    WORK_ANNIVERSARY = "work_anniversary"
    ONBOARDING_COMPLETE = "onboarding_complete"
    WELLNESS_ALERT = "wellness_alert"
    BURNOUT_RISK = "burnout_risk"
    ENGAGEMENT_LOW = "engagement_low"
    BUDDY_ASSIGNED = "buddy_assigned"
    SURVEY_COMPLETED = "survey_completed"


class WebhookStatus(str, enum.Enum):
    """Status of a webhook."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"


class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    url = Column(Text, nullable=False)
    secret = Column(String(128), nullable=True)
    event_type = Column(String(64), nullable=False, index=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(String(16), default=WebhookStatus.ACTIVE.value, nullable=False)
    
    # Retry configuration
    max_retries = Column(Integer, default=3, nullable=False)
    retry_delay_seconds = Column(Integer, default=60, nullable=False)
    
    # Request configuration
    method = Column(String(8), default="POST", nullable=False)
    headers = Column(Text, nullable=True)  # JSON string for custom headers
    
    # Stats
    total_requests = Column(Integer, default=0, nullable=False)
    successful_requests = Column(Integer, default=0, nullable=False)
    failed_requests = Column(Integer, default=0, nullable=False)
    last_triggered_at = Column(DateTime, nullable=True)
    last_successful_at = Column(DateTime, nullable=True)
    last_failed_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    __table_args__ = (
        Index("ix_webhooks_user_event", "user_id", "event_type"),
        UniqueConstraint("user_id", "name", name="uq_webhooks_user_name"),
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id = Column(UUID(as_uuid=True), ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False, index=True)
    
    event_type = Column(String(64), nullable=False)
    payload = Column(Text, nullable=False)  # JSON string
    
    method = Column(String(8), default="POST", nullable=False)
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    
    attempt = Column(Integer, default=0, nullable=False)
    is_successful = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("ix_webhook_deliveries_webhook_created", "webhook_id", "created_at"),
    )


class SlackIntegration(Base):
    __tablename__ = "slack_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    slack_user_id = Column(String(32), nullable=True)
    slack_team_id = Column(String(32), nullable=True)
    access_token = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    notify_on_mood = Column(Boolean, default=True, nullable=False)
    notify_on_appreciation = Column(Boolean, default=True, nullable=False)
    notify_on_tickets = Column(Boolean, default=True, nullable=False)
    notify_on_calendar = Column(Boolean, default=False, nullable=False)
    notify_on_leave = Column(Boolean, default=True, nullable=False)
    
    dm_enabled = Column(Boolean, default=True, nullable=False)
    channel_notifications = Column(Boolean, default=False, nullable=False)
    notification_channel = Column(String(64), nullable=True)
    
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_slack_integrations_user"),
    )