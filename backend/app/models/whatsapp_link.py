"""Dynamic WhatsApp ↔ user binding.

The existing ``WHATSAPP_USER_MAP`` env var supports a static phone→email map
for early demos. This model lets each employee self-serve a binding from the
product UI: issue a short code, send it via WhatsApp, server pairs the phone
to the user.

Schema notes:
  * One row per user (PK on ``user_id``). Re-linking overwrites in place.
  * ``phone_e164`` is unique so a single phone can't shadow two users.
  * ``pending_code`` is set during issuance and cleared on successful pair.
  * ``status`` is the simple state machine: ``pending`` → ``linked`` → (unlinked = row deleted).
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UUID

from ..core.time import utcnow_naive
from ..database import Base


class WhatsappLink(Base):
    __tablename__ = "whatsapp_links"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    phone_e164 = Column(String(32), nullable=True, unique=True, index=True)
    pending_code = Column(String(32), nullable=True, unique=True, index=True)
    status = Column(String(16), nullable=False, default="pending")
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    linked_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
