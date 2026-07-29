# MARK — which screen calls which API

Reference for support and debugging: when a screen looks wrong, this says what
to check. Paths are relative to the API root (`/api/v1` unless noted).

Metric definitions live in [HR_METRICS.md](./HR_METRICS.md).

---

## HR screens

| Screen | Route | Primary endpoints |
|---|---|---|
| Pulse (dashboard) | `/dashboard` | `GET /analytics/dashboard`, `/analytics/kpis-with-deltas`, `/analytics/emotions`, `/analytics/departments-heatmap`, `/analytics/insights`; live via `GET /realtime/hr/stream` |
| Employees | `/employees` | `GET /analytics/employees`; per person `GET /analytics/attrition/{user_id}`, `/analytics/burnout/{user_id}` |
| Employee profile | `/employees/:id` | `GET /users/{id}`, `/portal/me/timeline` equivalents, `/mood/{user_id}` |
| Tickets | `/tickets` | `GET /tickets`, `PATCH /tickets/{id}/…`; live via `/realtime/hr/stream` |
| Requests | `/requests` | `GET /requests`, `/requests/summary`; actions `PATCH /requests/{id}/{approve\|reject\|schedule\|complete}` |
| Manager view | `/manager` | `GET /analytics/manager/dashboard`, `/analytics/manager/team`, `/analytics/manager/emotions` |
| Surveys | `/surveys` | `GET /surveys`, `POST /surveys`, responses under `/surveys/{id}` |
| Knowledge base | `/knowledge-base` | `GET/POST/DELETE /rag/documents` |
| Email assistant | `/email-assistant` | `POST /email/draft`, `POST /email/send` |
| Admin | `/admin` | `GET /users`, `/automations/rules`, `/integrations/providers`, `/integrations/{hrms\|payroll}/sync` |
| Billing | `/billing` | `GET /billing/subscription` |

## Employee screens

| Screen | Route | Primary endpoints |
|---|---|---|
| My Day | `/employee` | `GET /portal/me/summary`, `/portal/me/timeline`, `/leave` |
| Conversations | `/chat` | `POST /chat/conversations/start`, `POST /chat/conversations/{id}/respond/stream`, `GET /chat/nudges/pending`, `GET /chat/memory-cards`; live via `GET /realtime/me/stream` |
| Requests | `/requests` | `GET /requests?mine_only=true`, `PATCH /requests/{id}/cancel` |
| Room booking | `/rooms` | `GET /rooms`, `/rooms/{id}/availability`, `POST /rooms/book`, `GET /rooms/bookings/my` |

---

## Notes that save debugging time

**Chat uses the streaming endpoint, not `POST /chat/message`.** If you are
watching logs for chat traffic, look for
`POST /chat/conversations/{id}/respond/stream`. `/chat/message` exists and works
but the web client does not use it.

**The employee transcript is restored from local storage, not the server.**
Server-side messages are not replayed into the thread. Proactive messages reach
a returning employee through `GET /chat/nudges/pending`, which the client polls
on open — so "the nudge never appeared" is usually a client-side question, not a
database one.

**`conversation_id` must be threaded by the caller.** Omitting it starts a new
conversation every message, which silently breaks any multi-step flow — the bot
re-asks its first question forever.

**Two SSE streams, different audiences.** `/realtime/hr/stream` is HR/admin only;
employees use `/realtime/me/stream`, which filters events to that user. Pointing
an employee view at the HR stream produces a 403 reconnect loop.

**Sentiment writes are deferred by default.**
`CHAT_DEFER_NONBLOCKING_SIDE_EFFECTS` runs the pipeline after the HTTP response,
so a score may briefly lag the message that caused it. Check
`sentiment_pipeline_failures_total` on `/metrics` before assuming a dashboard
bug.

**Operational endpoints.** `/healthz` liveness, `/readyz` dependency checks,
`/metrics` (HR/admin) for pipeline counters and HTTP errors by route.
