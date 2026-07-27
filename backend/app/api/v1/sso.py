"""SSO via OpenID Connect (OIDC).

Live when ``OIDC_CLIENT_ID`` / ``OIDC_CLIENT_SECRET`` / ``OIDC_ISSUER`` are set.
Uses the provider's discovery document (`/.well-known/openid-configuration`) to
locate endpoints, runs the standard authorization-code flow, links/provisions a
local user by verified email, and mints an ordinary MARK access token — so SSO
users are indistinguishable from password users downstream.

When OIDC isn't configured every endpoint degrades cleanly: ``/providers``
returns an empty list (the frontend hides the SSO button) and the login/callback
routes return 501 pointing at ``docs/SSO.md``.

SAML is intentionally not implemented; OIDC covers Okta, Azure AD, Auth0, Google
Workspace, Keycloak, etc. out of the box. Add a SAML branch here when a customer
specifically requires it.
"""
from __future__ import annotations

import logging
import os
import secrets
import time
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ...auth import create_access_token, hash_password
from ...database import get_db
from ...models.user import User, UserRole, UserStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sso", tags=["sso"])

_STATE_ALGO = "HS256"
_DOC_HINT = "SSO is not configured on this deployment. See docs/SSO.md."


def _secret() -> str:
    return os.getenv("SECRET_KEY", "your-secret-key-here")


def _oidc_config() -> dict | None:
    client_id = os.getenv("OIDC_CLIENT_ID", "").strip()
    client_secret = os.getenv("OIDC_CLIENT_SECRET", "").strip()
    issuer = os.getenv("OIDC_ISSUER", "").strip().rstrip("/")
    if not (client_id and client_secret and issuer):
        return None
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "issuer": issuer,
        "name": os.getenv("OIDC_PROVIDER_NAME", "SSO"),
        "scopes": os.getenv("OIDC_SCOPES", "openid email profile"),
        "provider_key": os.getenv("OIDC_PROVIDER_KEY", "oidc"),
    }


def _discover(issuer: str) -> dict:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{issuer}/.well-known/openid-configuration")
        resp.raise_for_status()
        return resp.json()


def _redirect_uri(request: Request, provider: str) -> str:
    override = os.getenv("OIDC_REDIRECT_URI", "").strip()
    if override:
        return override
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/sso/{provider}/callback"


def _frontend_login_url() -> str:
    base = os.getenv("FRONTEND_BASE_URL", "").rstrip("/")
    return f"{base}/login" if base else "/login"


@router.get("/providers")
def list_providers():
    """Return configured SSO providers, or an empty list when SSO is off."""
    cfg = _oidc_config()
    if not cfg:
        return {"providers": [], "enabled": False}
    return {"providers": [{"id": cfg["provider_key"], "name": cfg["name"]}], "enabled": True}


@router.get("/{provider}/login")
def initiate_login(provider: str, request: Request):
    """Begin the OIDC authorization-code flow: redirect the browser to the IdP."""
    cfg = _oidc_config()
    if not cfg:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_DOC_HINT)
    try:
        disc = _discover(cfg["issuer"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OIDC discovery failed: {exc}")

    redirect_uri = _redirect_uri(request, provider)
    # Signed, short-lived state — carries the redirect_uri + a nonce so the
    # callback can validate without server-side session storage.
    state = jwt.encode(
        {
            "p": provider,
            "rd": redirect_uri,
            "n": secrets.token_urlsafe(8),
            "purpose": "oidc_state",
            "exp": int(time.time()) + 600,
        },
        _secret(),
        algorithm=_STATE_ALGO,
    )
    params = {
        "client_id": cfg["client_id"],
        "response_type": "code",
        "scope": cfg["scopes"],
        "redirect_uri": redirect_uri,
        "state": state,
    }
    auth_url = f"{disc['authorization_endpoint']}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(auth_url, status_code=status.HTTP_302_FOUND)


@router.get("/{provider}/callback")
def handle_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Handle the IdP redirect: exchange code, resolve user, issue MARK token."""
    cfg = _oidc_config()
    if not cfg:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_DOC_HINT)
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"IdP returned error: {error}")
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing authorization code or state")

    try:
        claims = jwt.decode(state, _secret(), algorithms=[_STATE_ALGO])
        if claims.get("purpose") != "oidc_state" or claims.get("p") != provider:
            raise ValueError("state mismatch")
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired SSO state")

    redirect_uri = claims.get("rd") or _redirect_uri(request, provider)

    try:
        disc = _discover(cfg["issuer"])
        with httpx.Client(timeout=12.0) as client:
            token_resp = client.post(
                disc["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                },
                headers={"Accept": "application/json"},
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()

            userinfo: dict = {}
            access = tokens.get("access_token")
            ui_endpoint = disc.get("userinfo_endpoint")
            if ui_endpoint and access:
                ui = client.get(ui_endpoint, headers={"Authorization": f"Bearer {access}"})
                if ui.status_code == 200:
                    userinfo = ui.json()
            # Fall back to id_token claims for email/name if userinfo is thin.
            if not userinfo.get("email") and tokens.get("id_token"):
                try:
                    id_claims = jwt.get_unverified_claims(tokens["id_token"])
                    userinfo = {**id_claims, **userinfo}
                except JWTError:
                    pass
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OIDC token exchange failed: {exc}")

    email = str(userinfo.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OIDC provider did not return an email")
    if userinfo.get("email_verified") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is not verified at the IdP")

    name = str(userinfo.get("name") or userinfo.get("preferred_username") or email.split("@")[0])

    user = db.query(User).filter(User.email == email).first()
    if not user:
        if os.getenv("OIDC_AUTO_PROVISION", "true").lower() not in ("1", "true", "yes"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No MARK account exists for this email")
        user = User(
            name=name,
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(16)),
            role=UserRole.employee,
            status=UserStatus.active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("SSO auto-provisioned user %s via %s", email, provider)

    if user.status != UserStatus.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user account")

    app_token = create_access_token({"sub": str(user.id), "role": user.role.value})

    login_url = _frontend_login_url()
    sep = "&" if "?" in login_url else "?"
    return RedirectResponse(f"{login_url}{sep}sso_token={urllib.parse.quote(app_token)}", status_code=status.HTTP_302_FOUND)
