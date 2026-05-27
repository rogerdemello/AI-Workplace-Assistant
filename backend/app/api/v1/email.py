import asyncio
import os
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Optional
from sqlalchemy.orm import Session

from ...database import get_db
from ...auth import get_current_user
from ...models.user import User
from ...models.ticket import Ticket, TicketPriority, TicketStatus
from ...models.hr_notification import HrNotification
from ...services import webhook_service
from ...services.automation_rules import AutomationRulesService
from ...services.email_draft import EmailDraftService, EMAIL_TYPES, TONES
from ...services.email_sender import EmailSenderError, send_email_via_smtp
from ...services.realtime_bus import realtime_bus

router = APIRouter(prefix="/email", tags=["email"])


class EmailDraftRequest(BaseModel):
    type: str
    tone: str
    context: Optional[Dict] = {}
    conversation_id: Optional[UUID] = None


class EmailDraftResponse(BaseModel):
    subject: str
    body: str
    tone: str
    type: str
    context: Dict
    grounded_in_conversation: bool = False


class EmailSendRequest(BaseModel):
    to: str
    subject: str
    body: str
    cc: list[str] = []


class EmailSendResponse(BaseModel):
    detail: str


class InboundEmailRequest(BaseModel):
    provider: str
    from_email: str
    to_email: str
    subject: str
    body: str
    message_id: Optional[str] = None


def _publish_hr_realtime(event_type: str, payload: dict) -> None:
    try:
        asyncio.run(realtime_bus.publish(event_type, payload))
    except Exception:
        pass


@router.post("/draft", response_model=EmailDraftResponse)
def create_email_draft(
    request: EmailDraftRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if request.type not in EMAIL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid email type. Must be one of: {EMAIL_TYPES}"
        )
    
    if request.tone not in TONES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tone. Must be one of: {TONES}"
        )
    
    service = EmailDraftService(db=db, user_id=current_user.id)
    try:
        draft = service.generate_draft(
            request.type,
            request.tone,
            request.context,
            conversation_id=request.conversation_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not generate email draft right now: {str(exc)}",
        ) from exc
    try:
        webhook_service.trigger_webhooks(
            db=db,
            event_type="email_draft_created",
            payload={
                "user_id": str(current_user.id),
                "email_type": request.type,
                "tone": request.tone,
            },
        )
    except Exception:
        # Do not fail user flow on webhook errors.
        pass
    
    return EmailDraftResponse(**draft)


@router.post("/send", response_model=EmailSendResponse)
def send_email(
    request: EmailSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        send_email_via_smtp(
            to=request.to.strip(),
            subject=request.subject.strip() or "No subject",
            body=request.body,
            cc=[v.strip() for v in request.cc if v.strip()],
        )
    except EmailSenderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    try:
        webhook_service.trigger_webhooks(
            db=db,
            event_type="email_sent",
            payload={
                "user_id": str(current_user.id),
                "to": request.to.strip(),
                "cc_count": len([v for v in request.cc if v.strip()]),
                "subject": request.subject.strip() or "No subject",
            },
        )
    except Exception:
        # Do not fail user flow on webhook errors.
        pass
    _publish_hr_realtime("hr_email_sent", {"to": request.to.strip(), "subject": request.subject.strip() or "No subject"})
    return EmailSendResponse(detail=f"Email sent by {current_user.email}")


@router.post("/inbound", status_code=status.HTTP_202_ACCEPTED)
def receive_inbound_email(
    payload: InboundEmailRequest,
    x_email_hook_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    configured_secret = os.getenv("EMAIL_HOOK_SECRET", "").strip()
    if configured_secret and x_email_hook_secret != configured_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid inbound hook secret")

    target_user = db.query(User).filter(User.email == payload.to_email.strip().lower()).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user matched inbound recipient. Ensure to_email maps to an employee account.",
        )

    query = f"[Inbound email] {payload.subject.strip()}\n\n{payload.body.strip()}"
    ticket = Ticket(
        user_id=target_user.id,
        query=query[:5000],
        category="email_inbound",
        status=TicketStatus.open,
        priority=TicketPriority.medium,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    db.add(
        HrNotification(
            ticket_id=ticket.id,
            actor_id=None,
            title="Inbound email converted to ticket",
            body=f"From {payload.from_email}: {payload.subject}",
            notification_type="email_inbound",
            severity="info",
        )
    )
    db.commit()

    try:
        AutomationRulesService(db).apply_event_rules(
            event_type="email_received",
            context={
                "ticket": ticket,
                "user_id": target_user.id,
                "from_email": payload.from_email,
                "subject": payload.subject,
                "message_id": payload.message_id or "",
                "provider": payload.provider,
            },
        )
        db.commit()
    except Exception:
        db.rollback()

    try:
        webhook_service.trigger_webhooks(
            db=db,
            event_type="email_received",
            payload={
                "ticket_id": str(ticket.id),
                "provider": payload.provider,
                "from_email": payload.from_email,
                "to_email": payload.to_email,
                "message_id": payload.message_id or "",
            },
        )
    except Exception:
        pass

    _publish_hr_realtime("hr_email_received", {"ticket_id": str(ticket.id), "from_email": payload.from_email})
    return {"status": "accepted", "ticket_id": str(ticket.id)}
