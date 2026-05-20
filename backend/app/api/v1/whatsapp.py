"""WhatsApp self-service linking endpoints.

Lets an authenticated employee pair their WhatsApp number to their MARK
account in three steps:

  1. ``POST /api/v1/whatsapp/link/start`` returns a short code.
  2. User sends that code from WhatsApp to MARK's Twilio number.
  3. ``GET /api/v1/whatsapp/link/status`` reflects the linked phone.

Unlink is a single ``DELETE /api/v1/whatsapp/link``.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...database import get_db
from ...models.user import User
from ...services.v2.whatsapp_link import (
    CODE_TTL_MINUTES,
    get_link,
    issue_code,
    mask_phone,
    unlink,
)


router = APIRouter(prefix="/whatsapp/link", tags=["whatsapp"])


class LinkIssueResponse(BaseModel):
    code: str
    expires_at: datetime
    ttl_minutes: int
    instructions: str


class LinkStatusResponse(BaseModel):
    status: str  # "unlinked" | "pending" | "linked"
    phone_masked: str | None = None
    linked_at: datetime | None = None
    pending_code: str | None = None
    expires_at: datetime | None = None


def _instructions() -> str:
    return (
        f"Send this code as a WhatsApp message to MARK's number. The code "
        f"expires in {CODE_TTL_MINUTES} minutes."
    )


@router.post("/start", response_model=LinkIssueResponse)
def start_link(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    link = issue_code(db, current_user.id)
    return LinkIssueResponse(
        code=link.pending_code or "",
        expires_at=link.expires_at,
        ttl_minutes=CODE_TTL_MINUTES,
        instructions=_instructions(),
    )


@router.get("/status", response_model=LinkStatusResponse)
def link_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    link = get_link(db, current_user.id)
    if link is None:
        return LinkStatusResponse(status="unlinked")
    return LinkStatusResponse(
        status=link.status,
        phone_masked=mask_phone(link.phone_e164),
        linked_at=link.linked_at,
        pending_code=link.pending_code if link.status == "pending" else None,
        expires_at=link.expires_at,
    )


@router.delete("")
def unlink_whatsapp(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not unlink(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No WhatsApp link to remove.",
        )
    return {"ok": True}
