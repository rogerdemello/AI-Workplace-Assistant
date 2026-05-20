"""SSO (SAML / OIDC) integration stub.

This module defines the API surface a real SSO integration would expose, but
does not implement the protocols themselves. Each endpoint returns 501 with a
hint pointing at ``docs/SSO.md``. Wire a real implementation when the first
customer asks for SSO — at that point you'll have a concrete identity
provider to design against (Okta, Azure AD, Auth0, etc.) and the trade-offs
become real instead of speculative.

The stub is intentionally cheap so:
  * Customers running compliance reviews see SSO as part of the API surface.
  * Real implementation slots into known endpoints, no router migration.
  * Frontend can probe ``/api/v1/sso/providers`` and hide the SSO button when
    the list is empty (no fake "Continue with SSO" affordance).
"""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/sso", tags=["sso"])


_DOC_HINT = (
    "SSO is not configured on this deployment. See docs/SSO.md for the "
    "integration plan."
)


@router.get("/providers")
def list_providers():
    """Return the configured SSO providers, or an empty list when not enabled."""
    # Real implementation: read from settings / DB and surface display names.
    return {"providers": [], "enabled": False}


@router.get("/{provider}/login")
def initiate_login(provider: str):
    """Kick off the SSO redirect dance. Stub returns 501."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_DOC_HINT)


@router.post("/{provider}/callback")
def handle_callback(provider: str):
    """Receive the IdP callback (SAMLResponse / OIDC code). Stub returns 501."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_DOC_HINT)
