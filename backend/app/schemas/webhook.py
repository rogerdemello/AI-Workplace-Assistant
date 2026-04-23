from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from uuid import UUID
from datetime import datetime


class WebhookCreate(BaseModel):
    name: str = Field(..., description="Webhook name")
    url: str = Field(..., description="Webhook URL")
    event_type: str = Field(..., description="Event type to trigger on")
    method: str = Field(default="POST", description="HTTP method")
    max_retries: int = Field(default=3, description="Max retry attempts")
    retry_delay_seconds: int = Field(default=60, description="Delay between retries")
    headers: Optional[Dict] = Field(default=None, description="Custom headers")


class WebhookUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Webhook name")
    url: Optional[str] = Field(None, description="Webhook URL")
    is_active: Optional[bool] = Field(None, description="Whether webhook is active")
    event_type: Optional[str] = Field(None, description="Event type to trigger on")
    max_retries: Optional[int] = Field(None, description="Max retry attempts")
    retry_delay_seconds: Optional[int] = Field(None, description="Delay between retries")
    method: Optional[str] = Field(None, description="HTTP method")
    headers: Optional[Dict] = Field(None, description="Custom headers")


class WebhookResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    url: str
    event_type: str
    is_active: bool
    status: str
    max_retries: int
    retry_delay_seconds: int
    method: str
    headers: Optional[Dict] = None
    total_requests: int
    successful_requests: int
    failed_requests: int
    last_triggered_at: Optional[datetime] = None
    last_successful_at: Optional[datetime] = None
    last_failed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookEventTypeResponse(BaseModel):
    event_type: str
    description: str
    available: bool


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    webhook_id: UUID
    event_type: str
    payload: Dict
    method: str
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    attempt: int
    is_successful: bool
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SlackConfigCreate(BaseModel):
    notify_on_mood: bool = Field(default=True, description="Notify on mood logs")
    notify_on_appreciation: bool = Field(default=True, description="Notify on appreciation notes")
    notify_on_tickets: bool = Field(default=True, description="Notify on ticket updates")
    notify_on_calendar: bool = Field(default=False, description="Notify on calendar events")
    notify_on_leave: bool = Field(default=True, description="Notify on leave requests")
    dm_enabled: bool = Field(default=True, description="Send direct messages")
    channel_notifications: bool = Field(default=False, description="Send to channel")
    notification_channel: Optional[str] = Field(None, description="Channel ID for notifications")


class SlackConfigUpdate(BaseModel):
    notify_on_mood: Optional[bool] = None
    notify_on_appreciation: Optional[bool] = None
    notify_on_tickets: Optional[bool] = None
    notify_on_calendar: Optional[bool] = None
    notify_on_leave: Optional[bool] = None
    dm_enabled: Optional[bool] = None
    channel_notifications: Optional[bool] = None
    notification_channel: Optional[str] = None
    is_active: Optional[bool] = None


class SlackConfigResponse(BaseModel):
    id: UUID
    user_id: UUID
    slack_user_id: Optional[str] = None
    slack_team_id: Optional[str] = None
    is_active: bool
    notify_on_mood: bool
    notify_on_appreciation: bool
    notify_on_tickets: bool
    notify_on_calendar: bool
    notify_on_leave: bool
    dm_enabled: bool
    channel_notifications: bool
    notification_channel: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}