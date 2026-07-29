# SSO Integration

MARK does not ship a configured SSO provider. The endpoints under
`/api/v1/sso/*` (see `app/api/v1/sso.py`) return 501 by default.

## When to wire this up

Wait for the first customer that explicitly asks for SSO. Until then the
stub keeps the API surface honest (compliance reviews see SSO listed,
frontend probes a real endpoint) without committing to a protocol or
identity provider.

## Endpoints

| Path | Stub behaviour | Real behaviour |
|---|---|---|
| `GET /api/v1/sso/providers` | Returns `{providers: [], enabled: false}` | Returns provider display names + sign-in URLs from settings/DB |
| `GET /api/v1/sso/{provider}/login` | 501 | Redirects to the IdP authorization URL with state + nonce |
| `POST /api/v1/sso/{provider}/callback` | 501 | Validates the IdP response, mints a MARK JWT, returns it as the existing `/auth/login` shape |

## Implementation sketch

1. **Pick a library**:
   - SAML: `python3-saml` (covers SP-initiated flows, signature checks).
   - OIDC: `authlib` — simpler than rolling your own with `requests-oauthlib`.
2. **Persist provider config** in a new `sso_providers` table (one row per
   tenant + provider). Fields: provider type, display name, metadata URL or
   raw IdP metadata, client_id/secret (encrypted via `EncryptedText`),
   default role mapping.
3. **Reuse the existing JWT flow**: the callback endpoint should mint a
   token using `app.auth.create_access_token(user_id, role)` — same shape
   the password login emits — so the rest of the app needs zero changes.
4. **Provision users on first login** by matching the IdP email against
   `users.email`. Refuse SSO logins for unknown emails by default; opt-in
   `auto_provision` per provider when the customer wants self-serve onboarding.
5. **Add a frontend toggle** that calls `GET /api/v1/sso/providers` at the
   login screen and renders a "Continue with {display_name}" button per
   entry. Hide the local password form when the deployment is SSO-only.

## Threat model notes

- Validate the IdP signature on every callback — never trust the request
  body alone.
- Bind `state` to the user's browser session via a short-lived signed cookie.
- Rate-limit `/callback` separately from the rest of the API to blunt
  credential-stuffing-via-SSO attacks.
- Capture audit log entries (the new `audit_logs` table picks these up for
  free under `AUDITED_PATH_PREFIXES`) for both successful and failed
  callbacks.
