"""HR access: Supabase JWT or dev header X-User-Role."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from ..config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)
_SUPABASE_JWT_AUDIENCE = "authenticated"


def _extract_app_role(payload: dict[str, Any]) -> Optional[str]:
    app_meta = payload.get("app_metadata") or {}
    user_meta = payload.get("user_metadata") or {}
    role = app_meta.get("role") or user_meta.get("role")
    if isinstance(role, str):
        return role.lower()
    return None


def decode_supabase_jwt(token: str) -> dict[str, Any]:
    if not settings.SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase JWT verification is not configured (SUPABASE_JWT_SECRET)",
        )
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience=_SUPABASE_JWT_AUDIENCE,
            options={"verify_aud": True},
        )
    except JWTError as e:
        logger.info("JWT verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from e


def _is_hr_role(role: Optional[str]) -> bool:
    return role in ("hr", "admin", "human_resources")


def get_hr_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
) -> dict[str, Any]:
    if credentials and credentials.credentials:
        payload = decode_supabase_jwt(credentials.credentials)
        role = _extract_app_role(payload)
        if not _is_hr_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HR or admin role required",
            )
        return {
            "sub": payload.get("sub"),
            "role": role or "hr",
            "email": payload.get("email"),
            "jwt_payload": payload,
        }

    if settings.ALLOW_HEADER_ROLE_AUTH and (x_user_role or "").lower() == "hr":
        return {
            "sub": "header-auth",
            "role": "hr",
            "email": None,
            "jwt_payload": None,
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing Bearer token or valid HR credentials",
    )


require_hr = get_hr_context
