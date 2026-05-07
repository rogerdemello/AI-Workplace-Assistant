# Release Checklist

Use this checklist before shipping a new build.

## 1) Environment and secrets

- [ ] `DATABASE_URL` points to the intended environment.
- [ ] `SECRET_KEY` is set and not default.
- [ ] Azure OpenAI variables are configured (`AZURE_OPENAI_*`).
- [ ] SMTP variables are configured (`SMTP_*`) for email sending.
- [ ] `FAST_CHAT_MODE` is set intentionally (`true` for low-latency mode).

## 2) Database readiness

- [ ] Run Alembic migrations:
  - `cd backend`
  - `alembic upgrade head`
- [ ] Confirm latest tables exist:
  - `ticket_action_logs`
  - `hr_notifications`
  - `ticket_messages.is_internal`

## 3) Backend verification

- [ ] Run full backend tests:
  - `cd backend`
  - `pytest`
- [ ] Confirm key workflow tests pass:
  - tickets, action logs, related issues
  - HR notifications list/read
  - leave and portal flows
  - chat hardening and intent switching

## 4) Frontend verification

- [ ] Build frontend:
  - `cd new-frontend`
  - `npm run build`
- [ ] Run frontend tests:
  - `npm run test -- --run`
- [ ] Manual smoke checks:
  - HR login -> Tickets -> Decision panel actions
  - Related issues button fetches real related tickets
  - Topbar notifications show for HR/Admin only
  - Email assistant draft/send path works with SMTP backend

## 5) RBAC checks

- [ ] Employee cannot access HR-only endpoints (`/portal/hr/*`, `/tickets/*/actions`, `/tickets/*/related`).
- [ ] HR/Admin can access ticket actions, related tickets, and notifications.
- [ ] Billing endpoint is HR/Admin-only.

## 6) Performance and stability checks

- [ ] Chat responses are timely in `FAST_CHAT_MODE`.
- [ ] UI handles API failures with safe fallbacks (no crashes).
- [ ] Dashboard and tickets load without blocking errors.

## 7) Final go-live review

- [ ] No sensitive values committed.
- [ ] `.env.example` documents required variables.
- [ ] Rollback path documented (previous image/tag + DB backup strategy).
- [ ] Team sign-off from Product + Engineering.
