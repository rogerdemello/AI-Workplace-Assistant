# MARK — AI Workplace Assistant

MARK is an AI-native HR and employee intelligence platform: a floating chat
widget for employees, an analytics dashboard for HR, and a multi-agent
backend that runs sentiment, proactive nudges, complaint workflows, leave,
RAG-grounded policy answers, and integrations (WhatsApp, Google / Outlook
calendar, room booking).

The codebase is a FastAPI service and a Vite + React frontend designed to
ship as a dedicated deployment per customer.

## What's in the repo

| Path | Contents |
|---|---|
| `frontend/` | Vite + React + Tailwind + shadcn/ui app (employee, HR, manager, admin surfaces) |
| `backend/` | FastAPI service, SQLAlchemy models, multi-agent orchestration, sentiment pipeline, RAG, schedulers |
| `backend/app/workers/` | Opt-in Celery tasks (sentiment, proactive scans, webhook delivery) |
| `backend/alembic/` | Schema migrations — the only source of schema truth; run `alembic upgrade head` on deploy |
| `backend/scripts/` | Operational probes, retention, reseed, frontend/backend contract check |
| `backend/tests/` | pytest suite |
| `db/` | Bootstrap SQL for a fresh Postgres/Supabase project (`schema.sql`, `init.sql`) |
| `docs/` | Operator docs — `DEPLOY.md`, `SSO.md`, `WORKERS.md`, `DATA_RETENTION.md`, and `ROADMAP.md` |
| `scripts/` | Local dev launchers and release smoke helpers (`.ps1` / `.sh`) |
| `.github/workflows/` | CI (pytest, tsc, vite build, smoke E2E against SQLite) |

## Capabilities

### For employees

- Floating **chat widget** with streaming responses, attachments, quick
  actions, CSAT, and a persistent unread badge.
- **Leave** workflow with date validation, manager approval lifecycle, and
  60-day cap.
- **Complaint / ticket** flow with anonymous-by-flag support — anonymous
  tickets scrub `user_id` from HR-facing responses (`Ticket.is_anonymous`).
- **Policy Q&A** via RAG (sentence-aware chunking, BM25 + cosine hybrid
  retrieval, source attribution, freshness warnings).
- **WhatsApp link** — self-serve pairing via a short code so HR replies,
  leave decisions, and reminders reach the user's phone.
- **Calendar OAuth** — connect Google Calendar or Outlook for free/busy
  lookup and event creation.
- **Room booking** at `/rooms` with availability grid + cancel.

### For HR

- **Dashboard 2.0** at `/dashboard`:
  - KPI tiles with deltas vs prior period (`/analytics/kpis-with-deltas`)
  - Stacked sentiment trend chart with 7d / 30d / 90d range selector
  - Department × sentiment-bucket heatmap (`/analytics/departments-heatmap`)
  - Top-10 at-risk employees with sort toggle
  - Alerts panel grouped by severity from `hr_alerts`
  - AI insight feed
- **Ticket drawer 2.0** at `/tickets`:
  - LLM-generated summary, cached in Redis, refresh-able
  - Live SLA countdown with progress bar
  - Sentiment trajectory sparkline since ticket open
  - Action chips: Escalate / Schedule 1:1 / Loop in manager / Close
  - Auto-loaded "possibly related" tickets
- **Knowledge base** at `/knowledge-base` with stale-document badges (>365 days)
- **Audit log** middleware records every state-changing call on sensitive
  surfaces (tickets, leave, alerts, surveys, integrations, webhooks) into
  `audit_logs` — actor, method, path, target, payload SHA256, status, IP.

### Backend platform

- **Multi-agent orchestration**: analysis, emotional, proactive,
  productivity agents with confidence-scored overlays; moderation pass
  drops weak overlays and masks PII inside specialist output.
- **Sentiment pipeline**: hybrid LLM + lexicon, per-message logs,
  employee score aggregation, sustained-risk alerts.
- **Proactive engine**: APScheduler-driven (SLA escalation, silent users,
  break / lunch / wellness nudges, repeated-complaint detection, leave
  accrual).
- **Field-level encryption helper** (`app/core/encryption.py`) — opt-in
  Fernet `EncryptedText` column type for sensitive free-text fields.
- **SSO** stub (`/api/v1/sso/*`) — interface in place, real
  implementation guided by `docs/SSO.md`.
- **Schema-drift audit** at boot — warns when the live DB drifts from the
  latest Alembic head instead of silently diverging.

### Observability & ops

For HR: [what the numbers mean](docs/HR_METRICS.md) and
[which screen calls which API](docs/SCREEN_API_MAP.md).

- `/healthz` (liveness) and `/readyz` (DB / Redis / Azure OpenAI checks).
- `/metrics` (HR/admin only) — counters and latency for the sentiment pipeline
  (`sentiment_pipeline_processed_total`, `sentiment_pipeline_failures_total` by
  error type and sync/deferred path) and HTTP errors by route template. Values
  are per-process and reset on restart, so read them as "is this happening now",
  not as history. Pipeline failures are also logged as
  `event=sentiment_pipeline_failed` for log-based alerting.
- **Sentry** wiring on both backend (FastAPI integration) and frontend
  (dynamic import — no failure when SDK is absent). Set `SENTRY_DSN` /
  `VITE_SENTRY_DSN` to enable.
- **Opt-in Celery workers** for sentiment, proactive scans, and webhook
  delivery — driven by `CELERY_BROKER_URL`. Without a broker everything
  runs in-process exactly as before. See `docs/WORKERS.md`.

## Tech stack

| Layer | Tech |
|---|---|
| Backend | FastAPI 0.109, SQLAlchemy 2.0, Alembic, Pydantic 2 |
| LLM | Azure OpenAI (chat completions + embeddings); MockAzureOpenAIClient for tests |
| Storage | PostgreSQL (Supabase-compatible), SQLite for local dev |
| Cache / broker | Redis (in-memory fallback when absent) |
| Background | APScheduler in-process; optional Celery workers |
| RAG | pypdf + python-docx ingestion, rank-bm25, cosine similarity, Redis-cached chunk embeddings |
| Frontend | Vite 5, React 18, TypeScript, Tailwind, shadcn/ui, Recharts, Framer Motion |

## Local setup

1. Copy `.env.example` to `.env` and fill in the required service credentials.
2. Start the stack with Docker Compose or run the backend and frontend separately.

### Docker Compose

```bash
# Default: API + frontend + redis (no workers).
docker compose up --build

# Opt in to Celery workers — requires CELERY_BROKER_URL in .env.
docker compose --profile workers up --build
```

This starts:

- Backend API on `http://localhost:8000`
- Frontend on `http://localhost:8080`
- Redis on port `6379`
- Optionally a Celery worker (under the `workers` profile)

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

#### Database schema

SQLite (the default for local dev) builds its tables automatically on boot.

**Postgres schema is owned by Alembic** — `create_all` is deliberately not run
against it, so a new model does not silently materialise a table and leave
migrations drifting behind. Apply migrations as part of every deploy:

```bash
cd backend
alembic upgrade head
```

The boot-time schema audit logs a loud warning if the database is empty or the
stamped revision is behind the latest migration. Set `DB_CREATE_ALL=true` to
force `create_all` on Postgres for throwaway environments only.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Useful commands

```bash
# Seed demo users (emp1@mark.ai / hr1@mark.ai, password: password123)
cd backend
python -m scripts.seed_dummy_users

# Run the end-to-end smoke probe (login, chat, ticket, leave, sentiment, health)
python -m scripts.smoke_e2e

# Run the backend test suite
pytest

# Load probe: concurrent chat + HR analytics, reports p50/p95/p99 per endpoint.
# Point it at staging — a local SQLite backend measures SQLite, not production.
python -m scripts.loadtest --base-url https://staging.example.com \
    --employees 25 --hr 5 --duration 60

# Start a Celery worker (requires CELERY_BROKER_URL)
celery -A app.workers.celery_app.celery worker -l info -Q default
```

Browser end-to-end tests (Playwright) need both servers already running — see
the header of `frontend/playwright.config.ts` for the exact commands:

```bash
# 1. backend on :8099 (seeded), 2. vite on :8080, then:
cd frontend && npm run test:e2e
```

```bash
# Frontend type-check + production build
cd frontend
npx tsc --noEmit
npm run build
```

## Environment knobs

Most of MARK is feature-flagged. Some non-obvious ones:

| Env var | Effect |
|---|---|
| `SECRET_KEY` | **Required.** Signs session tokens; the app refuses to start if it is empty or still the repo placeholder |
| `ENABLE_DEMO_LOGIN` | Mounts the unauthenticated `POST /api/v1/demo/login` (issues HR-role tokens on request). Off by default; local demos only |
| `CELERY_BROKER_URL` | When set, sentiment / proactive / webhook tasks dispatch to Celery workers; otherwise they run inline |
| `MARK_ENCRYPTION_KEY` | URL-safe base64 Fernet key for `EncryptedText` columns; module is no-op when unset |
| `SENTRY_DSN` / `VITE_SENTRY_DSN` | Enables Sentry capture on backend / frontend; both fail-open when absent |
| `ENABLE_WHATSAPP_CHANNEL`, `TWILIO_*`, `WHATSAPP_VERIFY_TOKEN` | Enable WhatsApp inbound webhook + outbound notifications |
| `ENABLE_PRODUCTIVITY_AGENT`, `ENABLE_LIFE_ASSISTANT`, `ENABLE_MULTI_AGENT_ORCHESTRATION` | Toggle multi-agent specialists |
| `ENABLE_ALERT_BACKGROUND`, `ALERT_SCAN_INTERVAL_SECONDS` | Proactive wellbeing scan loop |
| `AZURE_OPENAI_*` | Real LLM-backed chat, RAG, sentiment, ticket summaries; mock client kicks in when key is `mock-key` |
| `WHATSAPP_USER_MAP` | Legacy static email→phone demo map; dynamic per-user `whatsapp_links` table is preferred |

## Health & probes

- `GET /healthz` — liveness, no dependencies
- `GET /readyz` — DB required, Redis + Azure OpenAI best-effort; returns 503 on DB failure
- `GET /health` — legacy alias, kept for back-compat
