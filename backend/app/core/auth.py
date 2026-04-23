"""HR access: accepts MARK app JWT (primary) or Supabase JWT (fallback) or dev header."""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

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


def _is_hr_role(role: Optional[str]) -> bool:
    return role in ("hr", "admin", "human_resources")


def _decode_mark_jwt(token: str) -> Optional[dict[str, Any]]:
    """Try to decode using the MARK app secret (same key used by auth.py)."""
    secret = settings.SECRET_KEY
    if not secret:
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
        return payload
    except JWTError:
        return None


def _decode_supabase_jwt(token: str) -> Optional[dict[str, Any]]:
    """Try to decode using the Supabase JWT secret (optional)."""
    if not settings.SUPABASE_JWT_SECRET:
        return None
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience=_SUPABASE_JWT_AUDIENCE,
            options={"verify_aud": True},
        )
    except JWTError:
        return None


def decode_supabase_jwt(token: str) -> dict[str, Any]:
    """Public compat shim — kept for callers outside this module."""
    result = _decode_supabase_jwt(token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase JWT verification is not configured (SUPABASE_JWT_SECRET)",
        )
    return result


def get_hr_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
) -> dict[str, Any]:
    """
    Resolve HR identity from:
    1. MARK app JWT (role field in payload) — used by demo login + standard auth
    2. Supabase JWT (app_metadata.role) — used when Supabase is connected
    3. X-User-Role header — development only (ALLOW_HEADER_ROLE_AUTH=true)
    """
    if credentials and credentials.credentials:
        token = credentials.credentials

        # ── 1. Try MARK app JWT first ──────────────────────────────────────────
        mark_payload = _decode_mark_jwt(token)
        if mark_payload:
            role = mark_payload.get("role", "").lower()
            if _is_hr_role(role):
                return {
                    "sub": mark_payload.get("sub"),
                    "role": role,
                    "email": mark_payload.get("email"),
                    "jwt_payload": mark_payload,
                }
            # Token valid but wrong role
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"HR or admin role required (got: {role or 'none'})",
            )

        # ── 2. Try Supabase JWT ────────────────────────────────────────────────
        supabase_payload = _decode_supabase_jwt(token)
        if supabase_payload:
            role = _extract_app_role(supabase_payload)
            if not _is_hr_role(role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="HR or admin role required",
                )
            return {
                "sub": supabase_payload.get("sub"),
                "role": role or "hr",
                "email": supabase_payload.get("email"),
                "jwt_payload": supabase_payload,
            }

        # Token present but couldn't decode with either key
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # ── 3. Dev header fallback ─────────────────────────────────────────────────
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
