"""HR auth check and session routing for SPAs."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from ..config import settings
from ..core.auth import decode_supabase_jwt, get_hr_context, security

router = APIRouter(tags=["hr-auth"])
legacy_router = APIRouter(tags=["hr-auth"], include_in_schema=False)


def _suggested_route_for_role(role: str) -> str:
    r = (role or "").lower()
    if r in ("hr", "admin", "human_resources"):
        return "/hr"
    if r in ("employee", "staff"):
        return "/employee"
    return "/"


def _session_from_token(credentials: Optional[HTTPAuthorizationCredentials]) -> dict[str, Any]:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    payload = decode_supabase_jwt(credentials.credentials)
    app_meta = payload.get("app_metadata") or {}
    user_meta = payload.get("user_metadata") or {}
    role = app_meta.get("role") or user_meta.get("role") or "employee"
    if isinstance(role, str):
        role = role.lower()
    return {
        "sub": payload.get("sub"),
        "role": role,
        "email": payload.get("email"),
    }


def _hr_auth_response(user: dict) -> dict[str, Any]:
    role = user.get("role", "hr")
    return {
        "authenticated": True,
        "user_id": user.get("sub"),
        "role": role,
        "suggested_route": _suggested_route_for_role(str(role)),
    }


@router.get("/auth-check")
def hr_auth_check(user: dict = Depends(get_hr_context)):
    return _hr_auth_response(user)


@legacy_router.get("/hr/auth-check")
def hr_auth_check_legacy(user: dict = Depends(get_hr_context)):
    return _hr_auth_response(user)


@router.get("/session")
def session_routing_hint(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
):
    if credentials and credentials.credentials:
        ctx = _session_from_token(credentials)
        role = str(ctx.get("role") or "employee")
        return {
            "authenticated": True,
            "user_id": ctx.get("sub"),
            "role": role,
            "suggested_route": _suggested_route_for_role(role),
        }

    if settings.ALLOW_HEADER_ROLE_AUTH and (x_user_role or "").lower() in (
        "hr",
        "employee",
    ):
        r = (x_user_role or "").lower()
        return {
            "authenticated": True,
            "user_id": None,
            "role": r,
            "suggested_route": _suggested_route_for_role(r),
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing session",
    )
