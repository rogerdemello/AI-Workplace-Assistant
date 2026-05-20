"""Generalized audit log for state-changing API calls.

Recorded by ``audit_log_middleware``. One row per state-changing request
(POST / PATCH / PUT / DELETE) on whitelisted path prefixes. The request body
is NOT stored — only a SHA-256 digest so we can prove "what payload was
sent" without keeping the bytes themselves.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UUID

from ..core.time import utcnow_naive
from ..database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    method = Column(String(8), nullable=False)
    path = Column(String(500), nullable=False, index=True)
    target_type = Column(String(64), nullable=True, index=True)
    target_id = Column(String(64), nullable=True, index=True)
    payload_sha256 = Column(String(64), nullable=True)
    status_code = Column(Integer, nullable=True)
    ip = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, index=True)
