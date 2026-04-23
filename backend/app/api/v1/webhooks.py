from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ...database import get_db
from ...schemas.webhook import (
    WebhookCreate, WebhookUpdate, WebhookResponse,
    WebhookDeliveryResponse, SlackConfigCreate, SlackConfigUpdate, SlackConfigResponse
)
from ...auth import get_current_user
from ...models.user import User
from ...models.webhook import WebhookEventType
from ...services import webhook_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


WEBHOOK_EVENT_DESCRIPTIONS = {
    "mood_logged": "When a user logs their mood",
    "mood_trend_alert": "When mood trend shows decline",
    "appreciation_sent": "When appreciation note is sent",
    "appreciation_received": "When appreciation note is received",
    "ticket_created": "When a support ticket is created",
    "ticket_updated": "When a support ticket is updated",
    "ticket_resolved": "When a support ticket is resolved",
    "leave_requested": "When leave is requested",
    "leave_approved": "When leave is approved",
    "leave_rejected": "When leave is rejected",
    "birthday": "When it's an employee's birthday",
    "work_anniversary": "When an employee celebrates work anniversary",
    "onboarding_complete": "When new employee completes onboarding",
    "wellness_alert": "When wellness alert is triggered",
    "burnout_risk": "When burnout risk is detected",
    "engagement_low": "When employee engagement is low",
    "buddy_assigned": "When onboarding buddy is assigned",
    "survey_completed": "When survey is completed",
}


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
def create_webhook(
    webhook_data: WebhookCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if webhook_data.event_type not in WEBHOOK_EVENT_DESCRIPTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event_type. Must be one of: {list(WEBHOOK_EVENT_DESCRIPTIONS.keys())}"
        )
    
    record = webhook_service.create_webhook(
        db=db,
        user_id=current_user.id,
        name=webhook_data.name,
        url=webhook_data.url,
        event_type=webhook_data.event_type,
        method=webhook_data.method,
        max_retries=webhook_data.max_retries,
        retry_delay_seconds=webhook_data.retry_delay_seconds,
        headers=webhook_data.headers
    )
    return record


@router.get("", response_model=List[WebhookResponse])
def list_webhooks(
    event_type: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if event_type and event_type not in WEBHOOK_EVENT_DESCRIPTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event_type. Must be one of: {list(WEBHOOK_EVENT_DESCRIPTIONS.keys())}"
        )
    
    records = webhook_service.get_webhooks(db=db, user_id=current_user.id, event_type=event_type)
    return records


@router.get("/event-types", response_model=List[dict])
def list_event_types():
    return [
        {"event_type": event_type, "description": description}
        for event_type, description in WEBHOOK_EVENT_DESCRIPTIONS.items()
    ]


@router.get("/{webhook_id}", response_model=WebhookResponse)
def get_webhook(
    webhook_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = webhook_service.get_webhook(db=db, webhook_id=webhook_id)
    if not record:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    if str(record["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return record


@router.patch("/{webhook_id}", response_model=WebhookResponse)
def update_webhook(
    webhook_id: UUID,
    webhook_data: WebhookUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = webhook_service.get_webhook(db=db, webhook_id=webhook_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    if str(existing["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if webhook_data.event_type and webhook_data.event_type not in WEBHOOK_EVENT_DESCRIPTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event_type. Must be one of: {list(WEBHOOK_EVENT_DESCRIPTIONS.keys())}"
        )
    
    record = webhook_service.update_webhook(
        db=db,
        webhook_id=webhook_id,
        name=webhook_data.name,
        url=webhook_data.url,
        is_active=webhook_data.is_active,
        event_type=webhook_data.event_type,
        max_retries=webhook_data.max_retries,
        retry_delay_seconds=webhook_data.retry_delay_seconds,
        method=webhook_data.method,
        headers=webhook_data.headers
    )
    return record


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = webhook_service.get_webhook(db=db, webhook_id=webhook_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    if str(existing["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    webhook_service.delete_webhook(db=db, webhook_id=webhook_id)


@router.get("/{webhook_id}/deliveries", response_model=List[WebhookDeliveryResponse])
def get_webhook_deliveries(
    webhook_id: UUID,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = webhook_service.get_webhook(db=db, webhook_id=webhook_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    if str(existing["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    records = webhook_service.get_delivery_history(db=db, webhook_id=webhook_id, limit=limit)
    return records