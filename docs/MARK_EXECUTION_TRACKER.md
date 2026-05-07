# MARK Execution Tracker

Status legend: `DONE` / `PARTIAL` / `MISSING`

## 1) Core Foundation
- Chat-first interface: `PARTIAL` (floating widget, panel/full-screen, persistence done; backend SSE endpoint + frontend stream consumption added, true model-token streaming still pending)
- Authentication and roles: `DONE` (employee/hr roles, RBAC routes, protected UI)

## 2) Conversation Engine
- Intent detection: `DONE` (complaint/leave/policy/reminder/emotional/help/general)
- Slot filling and one-question flow: `DONE`
- Context switching and resume: `DONE` (switch acknowledgment + flow state)
- Memory quality filtering: `DONE` (noise filtering for yes/no style inputs)

## 3) Workflow Automation
- Complaint/tickets lifecycle + SLA + assignment + internal notes/replies: `DONE`
- Leave management end-to-end: `DONE`
- Reminder system (NL + recurring categories): `DONE` (employee dashboard now surfaces reminder history and reminder actions)

## 4) AI Intelligence Layer
- Sentiment per message + aggregates: `DONE`
- Mental health, engagement, risk, attrition scoring: `DONE` (calibrated attrition score + confidence band + factor-level explainability API + Employee profile explainability card)
- Manager effectiveness: `DONE` (backend metric + `/analytics/manager-effectiveness` + Admin UI surfacing)

## 5) Proactive Engine
- Time/behavior/emotional/health triggers: `PARTIAL` (event wiring expanded for `activity_event_tracked`, `reminder_created`, `reminder_updated`, `reminder_cancelled`; Admin now surfaces high-risk + weekly proactive rollup)
- Anti-spam suppression policy: `DONE` (HR/admin-configurable suppression policy API + Admin UI + enforced cooldown/daily caps)

## 6) RAG Knowledge System
- Retrieval and fallback: `DONE`
- Document upload/management operations UI: `DONE` (HR knowledge base page with upload/list/activate/delete + RBAC)

## 7) HR Dashboard
- KPI metrics, alerts, insights, employee table: `DONE`
- Chart depth and drill-down polish: `PARTIAL` (dashboard KPI/insight click-through now routes into filtered Employees/Tickets views via query params)

## 8) Ticket Management (HR)
- Decision panel, AI insight, suggested actions, context, thread/tags/duplicates: `DONE`

## 9) Employee Dashboard
- Minimal chat-first + my tickets/leave/reminders snapshot: `DONE` (mood trend + quick mood check-in + reminder panel integrated)

## 10) Manager Dashboard
- Team sentiment/risk + approvals/alerts: `DONE` (live risk/sentiment from snapshots + manager summary KPIs + support alerts + leave approvals)

## 11) Help Desk System
- Chat ticket creation + assignment + SLA + escalation: `DONE`

## 12) Automation Engine
- Auto workflows (create/process/escalate/alerts/check-ins): `PARTIAL` (now also wired for `ticket_reassigned`, `ticket_checkin_scheduled`, `ticket_internal_note_added`, `ticket_reply_posted`, `ticket_closed`, `leave_requested`, and reminder/activity lifecycle events; broader integrations still pending)

## 13) Integrations
- Calendar/email hooks: `DONE` (calendar OAuth + events live; email draft/send emits webhook hooks; new inbound mailbox webhook endpoint creates tickets, triggers automation + webhooks, and pushes realtime events)
- HRMS/payroll provider integrations: `PARTIAL` (provider catalog + sync endpoints now support env-gated live execution path with stub fallback; full provider-specific field mapping/auth refresh still pending)

## 14) UX / Design
- Chat-first responsive UI with animation: `DONE`
- Realtime push updates everywhere: `DONE` (SSE stream now combines heartbeat snapshots with in-process event-bus fanout from ticket/leave/email workflows for immediate refresh triggers)

## 15) System Behavior Rules
- Human-like, concise, contextual behavior guardrails: `PARTIAL` (strongly improved, still tuning edges)

---

## P0 Start Order (Execution)
1. Manager effectiveness scoring + dashboard surfacing.
2. Rule-configurable automation engine (admin-editable rules).
3. RAG document management completeness (upload/list/delete/status in HR UI).
4. Employee reminders/mood completeness in dashboard.
5. Realtime updates for notifications/tickets/dashboard cards.

## In Progress Right Now
- Time/behavior/emotional/health proactive trigger depth (cross-domain proactive rules + UI wiring).
