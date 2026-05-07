from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...auth import get_current_user, hash_password
from ...config import settings
from ...database import get_db
from ...models.user import User, UserRole, UserStatus
from ...schemas.chat import MessageSender
from ...services.chat import ChatService
from ...services.smart_chat import get_smart_chat_service
from xml.sax.saxutils import escape as xml_escape

from ...services.v2.capabilities import get_capabilities, normalize_whatsapp_sender, parse_whatsapp_user_map
from ...services.v2.whatsapp_session import get_or_resume_whatsapp_conversation

router = APIRouter(prefix="/workplace", tags=["workplace-v2"])


class CapabilitiesResponse(BaseModel):
    enable_whatsapp_channel: bool
    enable_life_assistant: bool
    enable_productivity_agent: bool


@router.get("/capabilities", response_model=CapabilitiesResponse)
def get_workplace_capabilities(_user: User = Depends(get_current_user)):
    capabilities = get_capabilities()
    return CapabilitiesResponse(
        enable_whatsapp_channel=capabilities.enable_whatsapp_channel,
        enable_life_assistant=capabilities.enable_life_assistant,
        enable_productivity_agent=capabilities.enable_productivity_agent,
    )


@router.get("/whatsapp/webhook")
def verify_whatsapp_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    if not settings.ENABLE_WHATSAPP_CHANNEL:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp channel disabled")
    if settings.WHATSAPP_VERIFY_TOKEN and hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(content=hub_challenge or "ok", media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verify token")


def _resolve_whatsapp_user(db: Session, from_number: str) -> User:
    normalized = normalize_whatsapp_sender(from_number or "")
    phone_map = parse_whatsapp_user_map(settings.WHATSAPP_USER_MAP)
    mapped_email = phone_map.get(normalized) or settings.WHATSAPP_DEFAULT_USER_EMAIL.strip().lower()
    user = db.query(User).filter(User.email == mapped_email).first()
    if user:
        return user
    user = User(
        id=uuid4(),
        email=mapped_email,
        name="WhatsApp User",
        employee_id=f"WSP-{uuid4().hex[:8].upper()}",
        hashed_password=hash_password("demo123"),
        role=UserRole.employee,
        status=UserStatus.active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/whatsapp/webhook")
def receive_whatsapp_message(
    Body: str = Form(default=""),
    From: str = Form(default=""),
    To: str = Form(default=""),
    db: Session = Depends(get_db),
):
    if not settings.ENABLE_WHATSAPP_CHANNEL:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp channel disabled")

    incoming_text = (Body or "").strip()
    if not incoming_text:
        return Response(
            content="<Response><Message>I did not catch that. Please send your message again.</Message></Response>",
            media_type="application/xml",
        )

    user = _resolve_whatsapp_user(db, From)
    chat_service = ChatService(db)
    conversation = get_or_resume_whatsapp_conversation(db, user.id, chat_service)
    smart_service = get_smart_chat_service(
        db=db,
        user_id=user.id,
        use_mock=False,
        conversation_id=conversation.id,
    )
    result = smart_service.process_message(incoming_text)
    reply = (result.get("response") or "I am here. How can I help?").strip()

    chat_service.add_message(
        conversation_id=conversation.id,
        message_text=f"[whatsapp] {incoming_text}",
        sender=MessageSender.user,
        sentiment=result.get("sentiment"),
    )
    chat_service.add_message(
        conversation_id=conversation.id,
        message_text=reply,
        sender=MessageSender.bot,
    )

    twiml = f"<Response><Message>{xml_escape(reply)}</Message></Response>"
    _ = To  # reserved for provider-specific routing in future slices
    return Response(content=twiml, media_type="application/xml")
