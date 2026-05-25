from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...auth import get_current_user, hash_password
from ...config import settings
from ...database import get_db
from ...models.user import User, UserRole, UserStatus
from ...schemas.chat import MessageSender
from ...services.chat import ChatService
from ...services.realtime_bus import realtime_bus
from ...services.smart_chat import get_smart_chat_service
from xml.sax.saxutils import escape as xml_escape

from ...services.v2.capabilities import get_capabilities, normalize_whatsapp_sender, parse_whatsapp_user_map
from ...services.v2.whatsapp_link import (
    CODE_TTL_MINUTES,
    consume_code,
    extract_code,
    find_user_by_phone,
)
from ...services.v2.whatsapp_session import get_or_resume_whatsapp_conversation

logger = logging.getLogger(__name__)


def _publish_realtime(event_type: str, payload: dict) -> None:
    try:
        asyncio.run(realtime_bus.publish(event_type, payload))
    except Exception:
        pass


def _validate_twilio_signature(request: Request, form_params: dict[str, str]) -> bool:
    """Validate Twilio's X-Twilio-Signature on an inbound webhook.

    Algorithm (per Twilio docs): HMAC-SHA1 over (full request URL +
    concat of sorted key+value pairs from the POST body), with the auth
    token as the key, base64-encoded.
    """
    auth_token = (settings.TWILIO_AUTH_TOKEN or "").encode("utf-8")
    if not auth_token:
        # Signature validation is on but we have no token to verify against —
        # safer to reject than to silently bypass.
        return False
    provided = request.headers.get("X-Twilio-Signature", "")
    if not provided:
        return False
    url = str(request.url)
    payload = url + "".join(f"{k}{form_params[k]}" for k in sorted(form_params))
    digest = hmac.new(auth_token, payload.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, provided)

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
    """Resolve the sender's MARK user.

    Resolution order:
      1. Dynamic ``whatsapp_links`` table (per-user self-serve binding).
      2. Static ``WHATSAPP_USER_MAP`` env var (legacy demo-mode mapping).
      3. ``WHATSAPP_DEFAULT_USER_EMAIL`` fallback (auto-provisions a stub user).

    Anyone who has linked their phone via the in-app flow takes precedence
    over any env-var mapping for that number — env vars are sticky and prone
    to drift, but a user's explicit binding is fresh.
    """
    dynamic_user_id = find_user_by_phone(db, from_number)
    if dynamic_user_id is not None:
        user = db.query(User).filter(User.id == dynamic_user_id).first()
        if user is not None:
            return user

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
async def receive_whatsapp_message(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    To: str = Form(default=""),
    db: Session = Depends(get_db),
):
    if not settings.ENABLE_WHATSAPP_CHANNEL:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp channel disabled")

    if settings.WHATSAPP_VALIDATE_SIGNATURE:
        form_dict = {k: (v if isinstance(v, str) else "") for k, v in (await request.form()).items()}
        if not _validate_twilio_signature(request, form_dict):
            logger.warning("Rejected inbound whatsapp webhook: bad signature from %s", From or "unknown")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    incoming_text = (Body or "").strip()
    if not incoming_text:
        return Response(
            content="<Response><Message>I did not catch that. Please send your message again.</Message></Response>",
            media_type="application/xml",
        )

    # If the message contains a MARK-XXXXXX pairing code, complete the link
    # *before* doing anything else. This is the one path that mutates the
    # phone↔user mapping, so it must run before the resolution step below.
    code = extract_code(incoming_text)
    if code:
        link = consume_code(db, code, From)
        if link is not None:
            user = db.query(User).filter(User.id == link.user_id).first()
            name = user.name if user else "there"
            confirm = (
                f"Hi {name}, your WhatsApp is now linked to MARK. "
                "You will receive HR updates here, and you can reply anytime."
            )
            return Response(
                content=f"<Response><Message>{xml_escape(confirm)}</Message></Response>",
                media_type="application/xml",
            )
        # Code was present but invalid / expired / claimed by another phone.
        # Tell the sender plainly so they can re-issue from the app.
        return Response(
            content=(
                "<Response><Message>"
                f"That code is not valid or has expired. Open MARK in the app, "
                f"request a new code, and send it within {CODE_TTL_MINUTES} minutes."
                "</Message></Response>"
            ),
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

    try:
        await realtime_bus.publish(
            "whatsapp_message_received",
            {
                "user_id": str(user.id),
                "conversation_id": str(conversation.id),
                "from_phone_masked": (From or "")[:-4] + "****" if From else "",
                "preview": incoming_text[:140],
            },
        )
    except Exception:
        pass

    twiml = f"<Response><Message>{xml_escape(reply)}</Message></Response>"
    _ = To  # reserved for provider-specific routing in future slices
    return Response(content=twiml, media_type="application/xml")
