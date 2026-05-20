# Async Workers

MARK ships an opt-in Celery layer for slow / IO-bound work. Without a broker
configured the API runs everything in-process, identical to the pre-Celery
deployment. Set one env var and you get worker-backed dispatch — no code
changes.

## When to enable

Turn this on when **any** of the following is true:

- Webhook deliveries to slow / flaky endpoints are starting to stretch
  request latency (the trigger fans out serially in-process).
- The hourly proactive wellbeing scan is bumping into the API process's
  event loop or eating DB pool slots.
- You're horizontally scaling the API (>1 uvicorn replica) and want
  background scans to fire exactly once rather than N times.

For a single-process solo deployment, **don't bother yet** — the inline path
is simpler to operate.

## Configuration

```bash
# Redis is the simplest broker — reuse the same instance the cache layer uses.
CELERY_BROKER_URL=redis://redis:6379/1

# Optional — only needed if you want to inspect task results from the API.
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

When `CELERY_BROKER_URL` is unset:

- `enqueue(task, ...)` calls the task body inline.
- Webhook fan-out is serial (one HTTP call after another).
- The proactive wellbeing loop in `main.py` runs the scan in-process.

When it's set:

- `enqueue(task, ...)` calls `.delay()` and returns an `AsyncResult`.
- Each webhook delivery becomes its own worker job; retries (3 attempts,
  30s backoff) happen on the worker.
- The proactive scan dispatches off the API loop entirely.

## Running a worker

```bash
cd backend
celery -A app.workers.celery_app.celery worker -l info -Q default
```

Workers need the same Python env + DB credentials + Azure OpenAI credentials
as the API. The simplest local setup:

```bash
# In one terminal
export CELERY_BROKER_URL=redis://localhost:6379/1
uvicorn app.main:app --reload

# In another
export CELERY_BROKER_URL=redis://localhost:6379/1
cd backend
celery -A app.workers.celery_app.celery worker -l info -Q default
```

## Tasks

| Task | Triggered by | Notes |
|---|---|---|
| `mark.process_sentiment_for_message` | (not wired by default — see below) | Re-runs the sentiment pipeline against a saved Message. Two retries, 15s backoff. |
| `mark.run_proactive_wellbeing_scan` | `main.py` background loop | One row per `hr_alert` produced. No retry — re-runs on the next interval anyway. |
| `mark.deliver_webhook` | `WebhookService.trigger_webhook` fanout | 3 retries, 30s default delay. Falls back to the synchronous inline path if `.delay()` raises (broker outage). |

The sentiment task is intentionally **not** wired into the chat hot path
yet — the existing `CHAT_DEFER_NONBLOCKING_SIDE_EFFECTS` flag already runs
sentiment work via FastAPI `BackgroundTasks` after the response is sent,
which is good enough for a single API process. If you scale to multiple
API replicas and want sentiment work to land on a dedicated worker pool,
enqueue `mark.process_sentiment_for_message(message_id)` from the chat
save path.

## Docker Compose

Add this service alongside your existing `api` / `redis` / `db` blocks
when you're ready to enable workers in deploy:

```yaml
worker:
  build: ./backend
  command: celery -A app.workers.celery_app.celery worker -l info -Q default --concurrency=4
  environment:
    - DATABASE_URL=${DATABASE_URL}
    - REDIS_URL=${REDIS_URL}
    - CELERY_BROKER_URL=redis://redis:6379/1
    - AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
    - AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
    - AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT}
    - SECRET_KEY=${SECRET_KEY}
  depends_on:
    - redis
    - db
  restart: unless-stopped
```

Start with `--concurrency=4`; tune by watching queue depth and worker CPU.

## Observability

- Worker logs go to stdout with the same format as the API.
- Sentry (if `SENTRY_DSN` is set) automatically captures unhandled
  exceptions in worker tasks via the same backend SDK init the API uses.
- For deeper inspection install `flower` and run
  `celery -A app.workers.celery_app.celery flower` to get a queue dashboard.

## When NOT to enqueue

- Endpoints that need synchronous confirmation (e.g., paying a real money
  bill) — keep those inline.
- One-shot CLI scripts (`scripts/seed_dummy_users.py`, smoke tests) —
  they don't have workers to drain.
