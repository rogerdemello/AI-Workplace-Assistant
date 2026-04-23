# MARK — Execution Plan (Infeedo-Level Roadmap)

This document is the **single source of truth** for phased delivery. Each phase has **exit criteria** and **verification** commands.

## Principles (non-negotiable)

- **State machine owns flow**; LLM produces language only.
- **One active intent** per conversation until the flow completes or user explicitly cancels.
- **Validate before persist** (dates, enums, ownership).
- **Deduplicate** tickets and noisy memory writes.
- **Degrade gracefully** when AI/RAG/embeddings fail.

---

## Phase P0 — Stability & correctness (current sprint)

| ID | Workstream | Primary files | Exit criteria |
|----|------------|-----------------|---------------|
| P0.1 | Conversation engine | `backend/app/services/smart_chat.py`, `backend/app/api/v1/chat.py`, `backend/app/services/emotional_memory.py` | No intent loops; leave balance / reminder routing correct; junk memory filtered |
| P0.2 | Tickets | `backend/app/services/ticket.py`, `backend/app/api/v1/tickets.py` | Duplicate prevention; clean lifecycle PATCH |
| P0.3 | RAG / policy | `backend/app/services/rag_retrieve.py`, `backend/app/api/v1/rag.py`, `backend/app/ai_client/client.py`, `frontend/app/api/chat/policy/route.ts` | Keyword fallback; no 500 on embedding failure; user-facing fallback copy |
| P0.4 | Repo hygiene | `.gitignore` | No tracked `.next`, `*.tsbuildinfo`, duplicate app trees |

**Verify P0**

```bash
cd backend && python -m pytest tests/test_smart_chat_hardening.py tests/test_leave_cancel.py tests/test_rag_resilience.py -q
cd backend && python -m pytest tests -q
```

---

## Phase P1 — HR product surface

| ID | Workstream | Primary files | Exit criteria |
|----|------------|-----------------|---------------|
| P1.1 | HR ticket UI | `frontend/src/components/HrTicketManagement.tsx`, `frontend/src/lib/api.ts` | Resolve / Escalate / Manage wired; badges + SLA overdue |
| P1.2 | Dashboard | `backend/app/services/dashboard_analytics.py`, `backend/app/routes/hr_dashboard.py`, `frontend/app/dashboard/page.tsx` | Actionable summaries; risk formula; alerts with cooldown; 30s refresh + grouped insights |
| P1.3 | Employee leave | `frontend/app/employee/page.tsx`, `backend/app/api/v1/leave.py` | Status chips; cancel pending |

**Verify P1**

```bash
cd frontend && npm test
cd frontend && npm run lint
```

Frontend lint uses `frontend/.eslintrc.json` (`next/core-web-vitals`) so `next lint` runs **non-interactively** in CI and local shells.

---

## Phase P2 — Intelligence & scale

| ID | Workstream | Primary files | Exit criteria |
|----|------------|-----------------|---------------|
| P2.1 | Proactive / silent signals | `backend/app/services/mark_proactive.py`, `backend/app/services/proactive_wellbeing.py`, `backend/app/services/scheduler.py` | Scheduled jobs; HR alerts from inactivity/risk |
| P2.2 | Schema parity | `backend/schema.sql`, `db/schema.sql`, `backend/migrations/*.sql` | Fresh bootstrap + migrations documented |
| P2.3 | E2E confidence | `frontend/tests/e2e/*`, `frontend/playwright.config.ts` | CI-local server policy; stable redirects |

**Verify P2**

```bash
cd frontend && npm run test:e2e
```

---

## Dependency order

1. P0.1 → P0.3 (chat + tickets + RAG)  
2. P0.4  
3. P1.x  
4. P2.x  

---

## Definition of “MARK complete” (release bar)

- Chat completes **complaint**, **leave apply**, **leave balance**, **reminder**, **policy** without loops.
- Tickets created with enrichment; duplicates blocked.
- Dashboard shows **real** aggregates and **actionable** insight text.
- RAG answers or **clear fallback**; no unhandled embedding errors.
- HR can **assign / status / escalate / resolve** from UI.
- Test suite green for backend + frontend unit; e2e green in CI profile.

---

*Last updated: execution kickoff — see git history for implementation details.*
