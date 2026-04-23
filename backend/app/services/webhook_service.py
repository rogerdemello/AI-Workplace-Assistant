from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from uuid import UUID
import json
import secrets
import hashlib
import hmac
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_

from ..models.webhook import Webhook, WebhookDelivery, WebhookEventType, WebhookStatus, SlackIntegration
from ..core.time import utcnow_naive


class WebhookRecord:
    def __init__(self, id: UUID, user_id: UUID, name: str, url: str, event_type: str,
                 is_active: bool, status: str, max_retries: int, retry_delay_seconds: int,
                 method: str, headers: Optional[Dict], total_requests: int, successful_requests: int,
                 failed_requests: int, last_triggered_at: Optional[datetime], last_successful_at: Optional[datetime],
                 last_failed_at: Optional[datetime], last_error: Optional[str], created_at: datetime, updated_at: datetime):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.url = url
        self.event_type = event_type
        self.is_active = is_active
        self.status = status
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.method = method
        self.headers = headers
        self.total_requests = total_requests
        self.successful_requests = successful_requests
        self.failed_requests = failed_requests
        self.last_triggered_at = last_triggered_at
        self.last_successful_at = last_successful_at
        self.last_failed_at = last_failed_at
        self.last_error = last_error
        self.created_at = created_at
        self.updated_at = updated_at
    
    def to_dict(self) -> Dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "name": self.name,
            "url": self.url,
            "event_type": self.event_type,
            "is_active": self.is_active,
            "status": self.status,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "method": self.method,
            "headers": self.headers,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "last_successful_at": self.last_successful_at.isoformat() if self.last_successful_at else None,
            "last_failed_at": self.last_failed_at.isoformat() if self.last_failed_at else None,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class WebhookDeliveryRecord:
    def __init__(self, id: UUID, webhook_id: UUID, event_type: str, payload: Dict,
                 method: str, status_code: Optional[int], response_body: Optional[str],
                 attempt: int, is_successful: bool, error_message: Optional[str],
                 created_at: datetime, completed_at: Optional[datetime]):
        self.id = id
        self.webhook_id = webhook_id
        self.event_type = event_type
        self.payload = payload
        self.method = method
        self.status_code = status_code
        self.response_body = response_body
        self.attempt = attempt
        self.is_successful = is_successful
        self.error_message = error_message
        self.created_at = created_at
        self.completed_at = completed_at
    
    def to_dict(self) -> Dict:
        return {
            "id": str(self.id),
            "webhook_id": str(self.webhook_id),
            "event_type": self.event_type,
            "payload": self.payload,
            "method": self.method,
            "status_code": self.status_code,
            "response_body": self.response_body,
            "attempt": self.attempt,
            "is_successful": self.is_successful,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class WebhookService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_webhook(
        self,
        user_id: UUID,
        name: str,
        url: str,
        event_type: str,
        method: str = "POST",
        max_retries: int = 3,
        retry_delay_seconds: int = 60,
        headers: Optional[Dict] = None
    ) -> WebhookRecord:
        secret = secrets.token_urlsafe(32)
        
        webhook = Webhook(
            user_id=user_id,
            name=name,
            url=url,
            secret=secret,
            event_type=event_type,
            method=method,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            headers=json.dumps(headers) if headers else None
        )
        self.db.add(webhook)
        self.db.commit()
        self.db.refresh(webhook)
        
        return self._record_from_model(webhook)
    
    def get_webhooks(self, user_id: UUID, event_type: Optional[str] = None) -> List[WebhookRecord]:
        query = self.db.query(Webhook).filter(Webhook.user_id == user_id)
        
        if event_type:
            query = query.filter(Webhook.event_type == event_type)
        
        webhooks = query.order_by(desc(Webhook.created_at)).all()
        return [self._record_from_model(w) for w in webhooks]
    
    def get_webhook(self, webhook_id: UUID) -> Optional[WebhookRecord]:
        webhook = self.db.query(Webhook).filter(Webhook.id == webhook_id).first()
        if webhook:
            return self._record_from_model(webhook)
        return None
    
    def update_webhook(
        self,
        webhook_id: UUID,
        name: Optional[str] = None,
        url: Optional[str] = None,
        is_active: Optional[bool] = None,
        event_type: Optional[str] = None,
        max_retries: Optional[int] = None,
        retry_delay_seconds: Optional[int] = None,
        method: Optional[str] = None,
        headers: Optional[Dict] = None
    ) -> Optional[WebhookRecord]:
        webhook = self.db.query(Webhook).filter(Webhook.id == webhook_id).first()
        if not webhook:
            return None
        
        if name is not None:
            webhook.name = name
        if url is not None:
            webhook.url = url
        if is_active is not None:
            webhook.is_active = is_active
            webhook.status = WebhookStatus.ACTIVE.value if is_active else WebhookStatus.INACTIVE.value
        if event_type is not None:
            webhook.event_type = event_type
        if max_retries is not None:
            webhook.max_retries = max_retries
        if retry_delay_seconds is not None:
            webhook.retry_delay_seconds = retry_delay_seconds
        if method is not None:
            webhook.method = method
        if headers is not None:
            webhook.headers = json.dumps(headers)
        
        self.db.commit()
        self.db.refresh(webhook)
        
        return self._record_from_model(webhook)
    
    def delete_webhook(self, webhook_id: UUID) -> bool:
        webhook = self.db.query(Webhook).filter(Webhook.id == webhook_id).first()
        if not webhook:
            return False
        
        self.db.delete(webhook)
        self.db.commit()
        return True
    
    def trigger_webhook(self, event_type: str, payload: Dict) -> List[WebhookDeliveryRecord]:
        delivery_records = []
        
        webhooks = self.db.query(Webhook).filter(
            and_(
                Webhook.event_type == event_type,
                Webhook.is_active == True,
                Webhook.status == WebhookStatus.ACTIVE.value
            )
        ).all()
        
        for webhook in webhooks:
            delivery = self._deliver_webhook(webhook, event_type, payload)
            if delivery:
                delivery_records.append(delivery)
        
        return delivery_records
    
    async def _deliver_webhook_async(self, webhook: Webhook, event_type: str, payload: Dict) -> WebhookDeliveryRecord:
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event_type=event_type,
            payload=json.dumps(payload),
            method=webhook.method or "POST"
        )
        self.db.add(delivery)
        
        webhook.total_requests += 1
        webhook.last_triggered_at = utcnow_naive()
        
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Event": event_type,
                "X-Webhook-ID": str(webhook.id)
            }
            
            if webhook.secret:
                payload_str = json.dumps(payload)
                signature = hmac.new(
                    webhook.secret.encode(),
                    payload_str.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers["X-Webhook-Signature"] = f"sha256={signature}"
            
            custom_headers = {}
            if webhook.headers:
                custom_headers = json.loads(webhook.headers)
            headers.update(custom_headers)
            
            method = webhook.method or "POST"
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=webhook.url,
                    json=payload if method == "POST" else None,
                    headers=headers,
                    timeout=30.0
                )
            
            delivery.status_code = response.status_code
            delivery.response_body = response.text[:2000] if response.text else None
            delivery.is_successful = 200 <= response.status_code < 300
            delivery.attempt += 1
            
            if delivery.is_successful:
                webhook.successful_requests += 1
                webhook.last_successful_at = utcnow_naive()
            else:
                webhook.failed_requests += 1
                webhook.last_failed_at = utcnow_naive()
                webhook.last_error = f"HTTP {response.status_code}"
        
        except Exception as e:
            delivery.is_successful = False
            delivery.error_message = str(e)[:500]
            delivery.attempt += 1
            webhook.failed_requests += 1
            webhook.last_failed_at = utcnow_naive()
            webhook.last_error = str(e)[:500]
        
        delivery.completed_at = utcnow_naive()
        self.db.commit()
        self.db.refresh(delivery)
        
        return self._record_from_delivery(delivery)
    
    def _deliver_webhook(self, webhook: Webhook, event_type: str, payload: Dict) -> Optional[WebhookDeliveryRecord]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return None
            return asyncio.run(self._deliver_webhook_async(webhook, event_type, payload))
        except RuntimeError:
            return asyncio.run(self._deliver_webhook_async(webhook, event_type, payload))
    
    def get_delivery_history(
        self,
        webhook_id: UUID,
        limit: int = 50
    ) -> List[WebhookDeliveryRecord]:
        deliveries = self.db.query(WebhookDelivery).filter(
            WebhookDelivery.webhook_id == webhook_id
        ).order_by(desc(WebhookDelivery.created_at)).limit(limit).all()
        
        return [self._record_from_delivery(d) for d in deliveries]
    
    def get_delivery(self, delivery_id: UUID) -> Optional[WebhookDeliveryRecord]:
        delivery = self.db.query(WebhookDelivery).filter(
            WebhookDelivery.id == delivery_id
        ).first()
        if delivery:
            return self._record_from_delivery(delivery)
        return None
    
    def _record_from_model(self, webhook: Webhook) -> WebhookRecord:
        headers = None
        if webhook.headers:
            headers = json.loads(webhook.headers)
        
        return WebhookRecord(
            id=webhook.id,
            user_id=webhook.user_id,
            name=webhook.name,
            url=webhook.url,
            event_type=webhook.event_type,
            is_active=webhook.is_active,
            status=webhook.status,
            max_retries=webhook.max_retries,
            retry_delay_seconds=webhook.retry_delay_seconds,
            method=webhook.method,
            headers=headers,
            total_requests=webhook.total_requests,
            successful_requests=webhook.successful_requests,
            failed_requests=webhook.failed_requests,
            last_triggered_at=webhook.last_triggered_at,
            last_successful_at=webhook.last_successful_at,
            last_failed_at=webhook.last_failed_at,
            last_error=webhook.last_error,
            created_at=webhook.created_at,
            updated_at=webhook.updated_at
        )
    
    def _record_from_delivery(self, delivery: WebhookDelivery) -> WebhookDeliveryRecord:
        payload = {}
        if delivery.payload:
            payload = json.loads(delivery.payload)
        
        return WebhookDeliveryRecord(
            id=delivery.id,
            webhook_id=delivery.webhook_id,
            event_type=delivery.event_type,
            payload=payload,
            method=delivery.method,
            status_code=delivery.status_code,
            response_body=delivery.response_body,
            attempt=delivery.attempt,
            is_successful=delivery.is_successful,
            error_message=delivery.error_message,
            created_at=delivery.created_at,
            completed_at=delivery.completed_at
        )


def get_webhook_service(db: Session) -> WebhookService:
    return WebhookService(db)


def create_webhook(
    db: Session,
    user_id: UUID,
    name: str,
    url: str,
    event_type: str,
    method: str = "POST",
    max_retries: int = 3,
    retry_delay_seconds: int = 60,
    headers: Optional[Dict] = None
) -> Dict:
    service = WebhookService(db)
    record = service.create_webhook(
        user_id=user_id,
        name=name,
        url=url,
        event_type=event_type,
        method=method,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay_seconds,
        headers=headers
    )
    return record.to_dict()


def get_webhooks(db: Session, user_id: UUID, event_type: Optional[str] = None) -> List[Dict]:
    service = WebhookService(db)
    records = service.get_webhooks(user_id, event_type)
    return [r.to_dict() for r in records]


def get_webhook(db: Session, webhook_id: UUID) -> Optional[Dict]:
    service = WebhookService(db)
    record = service.get_webhook(webhook_id)
    return record.to_dict() if record else None


def update_webhook(
    db: Session,
    webhook_id: UUID,
    name: Optional[str] = None,
    url: Optional[str] = None,
    is_active: Optional[bool] = None,
    event_type: Optional[str] = None,
    max_retries: Optional[int] = None,
    retry_delay_seconds: Optional[int] = None,
    method: Optional[str] = None,
    headers: Optional[Dict] = None
) -> Optional[Dict]:
    service = WebhookService(db)
    record = service.update_webhook(
        webhook_id=webhook_id,
        name=name,
        url=url,
        is_active=is_active,
        event_type=event_type,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay_seconds,
        method=method,
        headers=headers
    )
    return record.to_dict() if record else None


def delete_webhook(db: Session, webhook_id: UUID) -> bool:
    service = WebhookService(db)
    return service.delete_webhook(webhook_id)


def trigger_webhooks(db: Session, event_type: str, payload: Dict) -> List[Dict]:
    service = WebhookService(db)
    records = service.trigger_webhook(event_type, payload)
    return [r.to_dict() for r in records]


def get_delivery_history(db: Session, webhook_id: UUID, limit: int = 50) -> List[Dict]:
    service = WebhookService(db)
    records = service.get_delivery_history(webhook_id, limit)
    return [r.to_dict() for r in records]


def get_delivery(db: Session, delivery_id: UUID) -> Optional[Dict]:
    service = WebhookService(db)
    record = service.get_delivery(delivery_id)
    return record.to_dict() if record else None