"""Outbound WhatsApp (Twilio) notifications for HR events — failures never raise to callers."""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from ...config import settings
from ...models.user import User
from .capabilities import reverse_whatsapp_email_to_phone

logger = logging.getLogger(__name__)


def _twilio_whatsapp_uri(raw: str) -> str:
    r = (raw or "").strip()
    if not r:
        return r
    if r.lower().startswith("whatsapp:"):
        return r
    num = r if r.startswith("+") else f"+{r.lstrip('+')}"
    return f"whatsapp:{num}"


def send_whatsapp_to_user(db: Session, user_id: UUID, body: str) -> bool:
    """
    Send a plain WhatsApp text if outbound is enabled, Twilio is configured,
    and the user's email appears in WHATSAPP_USER_MAP (reverse lookup → phone).
    """
    text = (body or "").strip()
    if not text:
        return False
    if not getattr(settings, "ENABLE_WHATSAPP_OUTBOUND", False):
        return False
    sid = (getattr(settings, "TWILIO_ACCOUNT_SID", "") or "").strip()
    token = (getattr(settings, "TWILIO_AUTH_TOKEN", "") or "").strip()
    from_raw = (getattr(settings, "TWILIO_WHATSAPP_FROM", "") or "").strip()
    if not sid or not token or not from_raw:
        return False

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.email:
        return False

    rev = reverse_whatsapp_email_to_phone(settings.WHATSAPP_USER_MAP)
    phone_key = rev.get(user.email.strip().lower())
    if not phone_key:
        return False

    to_uri = _twilio_whatsapp_uri(phone_key)
    from_uri = _twilio_whatsapp_uri(from_raw)
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                url,
                data={"To": to_uri, "From": from_uri, "Body": text[:1600]},
                auth=(sid, token),
            )
        if resp.status_code >= 400:
            logger.warning("Twilio WhatsApp send failed: %s %s", resp.status_code, resp.text[:500])
            return False
    except Exception as exc:
        logger.warning("Twilio WhatsApp send error: %s", exc)
        return False
    return True


def notify_leave_decision(db: Session, *, user_id: UUID, action: str, summary: str) -> None:
    action_l = action.lower()
    if action_l == "approved":
        msg = f"Your leave request was approved. {summary}"
    elif action_l == "rejected":
        msg = f"Your leave request was rejected. {summary}"
    elif action_l == "cancelled":
        msg = f"Your leave request was cancelled. {summary}"
    else:
        msg = summary
    send_whatsapp_to_user(db, user_id, msg)


def notify_ticket_update(
    db: Session,
    *,
    user_id: UUID,
    kind: str,
    summary: str,
    detail: str = "",
) -> None:
    k = kind.lower()
    if k == "hr_reply":
        base = "Update on your HR ticket"
    elif k == "closed":
        base = "Your HR ticket was closed"
    else:
        base = "HR ticket update"
    line = summary.strip()
    extra = detail.strip()
    msg = f"{base}: {line}" if line else base
    if extra:
        msg = f"{msg}. {extra}"[:1600]
    send_whatsapp_to_user(db, user_id, msg)
