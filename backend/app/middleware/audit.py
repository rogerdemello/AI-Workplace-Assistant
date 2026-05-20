"""Audit-log middleware for state-changing API calls.

Records one row per POST / PATCH / PUT / DELETE under whitelisted path
prefixes. Authentication is best-effort: if a JWT is present we capture the
actor, otherwise we still record the call with ``actor_id = NULL``.

Notes:
  * Request bodies are NOT persisted — only the SHA-256 digest, so the audit
    log can prove "this payload was sent" without becoming a PII reservoir.
  * Auditing is opt-in by path prefix so we don't hammer the DB on noisy
    surfaces like ``/api/v1/chat/message`` (one row per chat turn would
    dominate the table).
  * Failures inside the middleware never fail the request — audit gaps are
    preferable to outages.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional
from uuid import UUID

from fastapi import Request
from jose import JWTError, jwt

from ..config import settings
from ..database import SessionLocal
from ..models.audit_log import AuditLog

logger = logging.getLogger(__name__)


# Auditing is enabled when the request path starts with one of these prefixes
# AND the method mutates state. Add prefixes here as new sensitive surfaces
# ship — better to under-audit than to overwhelm the audit_logs table.
AUDITED_PATH_PREFIXES = (
    "/api/v1/tickets",
    "/api/v1/leave",
    "/api/v1/auth/register",
    "/api/v1/rag/documents",
    "/api/v1/alerts",
    "/api/v1/automations",
    "/api/v1/surveys",
    "/api/v1/integrations",
    "/api/v1/webhooks",
    "/api/v1/sso",
    "/hr/",
)

STATE_CHANGING_METHODS = {"POST", "PATCH", "PUT", "DELETE"}

# Match a UUID at the end of a path segment so we can extract a target_id
# without hardcoding every endpoint shape.
_UUID_RE = re.compile(
    r"/(?P<uuid>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?:/|$)"
)


def _should_audit(request: Request) -> bool:
    if request.method not in STATE_CHANGING_METHODS:
        return False
    path = request.url.path
    return any(path.startswith(p) for p in AUDITED_PATH_PREFIXES)


def _extract_actor_id(request: Request) -> Optional[UUID]:
    auth_header = request.headers.get("authorization") or ""
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},
        )
    except JWTError:
        return None
    sub = payload.get("sub") or payload.get("user_id")
    if not sub:
        return None
    try:
        return UUID(str(sub))
    except (ValueError, AttributeError):
        return None


def _derive_target(path: str) -> tuple[Optional[str], Optional[str]]:
    """Best-effort (target_type, target_id) from a path like /api/v1/tickets/<uuid>/escalate."""
    match = _UUID_RE.search(path)
    target_id = match.group("uuid") if match else None
    # First non-versioned segment after /api/v1 is usually the resource name.
    parts = [p for p in path.split("/") if p]
    target_type: Optional[str] = None
    if "v1" in parts:
        idx = parts.index("v1")
        if idx + 1 < len(parts):
            target_type = parts[idx + 1]
    elif parts:
        target_type = parts[0]
    return target_type, target_id


async def audit_log_middleware(request: Request, call_next):
    if not _should_audit(request):
        return await call_next(request)

    # Capture body once so downstream handlers can still read it.
    body_bytes = b""
    try:
        body_bytes = await request.body()
    except Exception:
        body_bytes = b""

    async def receive() -> dict:
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    request = Request(request.scope, receive=receive)

    response = await call_next(request)

    try:
        actor_id = _extract_actor_id(request)
        target_type, target_id = _derive_target(request.url.path)
        payload_hash = (
            hashlib.sha256(body_bytes).hexdigest() if body_bytes else None
        )
        ip = (request.client.host if request.client else None) or request.headers.get(
            "x-forwarded-for", ""
        ).split(",")[0].strip() or None

        db = SessionLocal()
        try:
            db.add(
                AuditLog(
                    actor_id=actor_id,
                    method=request.method,
                    path=request.url.path[:500],
                    target_type=target_type[:64] if target_type else None,
                    target_id=target_id[:64] if target_id else None,
                    payload_sha256=payload_hash,
                    status_code=getattr(response, "status_code", None),
                    ip=ip[:64] if ip else None,
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        # Never fail a request because of audit logging. Surface in logs
        # so the gap is visible.
        logger.exception("audit_log_middleware failed (non-fatal)")

    return response
