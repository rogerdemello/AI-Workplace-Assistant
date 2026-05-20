"""WhatsApp link lifecycle helpers.

Issuance, lookup, and completion live here so the route handler and the
inbound webhook can share one implementation.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ...core.time import utcnow_naive
from ...models.whatsapp_link import WhatsappLink


CODE_PREFIX = "MARK-"
CODE_TTL_MINUTES = 15
_CODE_RE = re.compile(rf"\b{CODE_PREFIX}([A-Z0-9]{{6}})\b", re.IGNORECASE)
_E164_RE = re.compile(r"^\+?[1-9]\d{6,14}$")


def _generate_code() -> str:
    # ``token_hex(3)`` gives 6 hex chars — short enough to type from a phone,
    # broad enough to make brute-forcing the daily window pointless.
    return CODE_PREFIX + secrets.token_hex(3).upper()


def _normalize_phone(raw: str) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.strip()
    if cleaned.lower().startswith("whatsapp:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    cleaned = re.sub(r"[^\d+]", "", cleaned)
    if not cleaned.startswith("+"):
        cleaned = "+" + cleaned.lstrip("+")
    return cleaned if _E164_RE.match(cleaned) else None


def issue_code(db: Session, user_id: UUID) -> WhatsappLink:
    """Create or refresh the pending code for ``user_id``."""
    link = db.query(WhatsappLink).filter(WhatsappLink.user_id == user_id).first()
    code = _generate_code()
    expires_at = utcnow_naive() + timedelta(minutes=CODE_TTL_MINUTES)
    if link is None:
        link = WhatsappLink(
            user_id=user_id,
            pending_code=code,
            status="pending",
            created_at=utcnow_naive(),
            expires_at=expires_at,
        )
        db.add(link)
    else:
        link.pending_code = code
        link.status = "pending"
        link.expires_at = expires_at
        # Re-issuing preserves any previously linked phone so a user who lost
        # their device and re-issues from another keeps continuity.
    db.commit()
    db.refresh(link)
    return link


def get_link(db: Session, user_id: UUID) -> Optional[WhatsappLink]:
    return db.query(WhatsappLink).filter(WhatsappLink.user_id == user_id).first()


def unlink(db: Session, user_id: UUID) -> bool:
    link = get_link(db, user_id)
    if link is None:
        return False
    db.delete(link)
    db.commit()
    return True


def find_user_by_phone(db: Session, phone_raw: str) -> Optional[UUID]:
    """Return the user_id linked to ``phone_raw``, or None when not paired."""
    phone = _normalize_phone(phone_raw)
    if not phone:
        return None
    link = (
        db.query(WhatsappLink)
        .filter(
            WhatsappLink.phone_e164 == phone,
            WhatsappLink.status == "linked",
        )
        .first()
    )
    return link.user_id if link else None


def extract_code(body: str) -> Optional[str]:
    """Return the first ``MARK-XXXXXX`` token in ``body``, uppercased."""
    if not body:
        return None
    match = _CODE_RE.search(body)
    return match.group(0).upper() if match else None


def consume_code(db: Session, code: str, phone_raw: str) -> Optional[WhatsappLink]:
    """Complete a binding when ``code`` is sent from ``phone_raw``.

    Returns the linked row on success. Returns ``None`` for unknown,
    expired, or already-consumed codes.
    """
    phone = _normalize_phone(phone_raw)
    if not phone:
        return None
    link = (
        db.query(WhatsappLink)
        .filter(WhatsappLink.pending_code == code.upper())
        .first()
    )
    if link is None:
        return None
    if link.expires_at and link.expires_at < utcnow_naive():
        return None

    # If another user already linked this phone, refuse — same phone can't
    # serve two identities.
    collision = (
        db.query(WhatsappLink)
        .filter(WhatsappLink.phone_e164 == phone, WhatsappLink.user_id != link.user_id)
        .first()
    )
    if collision is not None:
        return None

    link.phone_e164 = phone
    link.status = "linked"
    link.linked_at = utcnow_naive()
    link.pending_code = None
    link.expires_at = None
    db.commit()
    db.refresh(link)
    return link


def mask_phone(phone: Optional[str]) -> Optional[str]:
    """Mask a phone for HR-facing display: keep country code + last 2 digits."""
    if not phone:
        return None
    if len(phone) <= 4:
        return "***"
    return f"{phone[:3]}***{phone[-2:]}"
