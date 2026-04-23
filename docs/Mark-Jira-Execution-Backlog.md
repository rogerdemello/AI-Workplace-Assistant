# MARK Intelligent Workplace Agent
## Jira Execution Backlog (Sprint-Ready)

Version: 1.0  
Date: April 13, 2026

## 1. Execution Scope

This backlog is an execution delta focused on shipping MARK differentiators:

- Layer 2 workplace assistant tools
- Layer 3 wellbeing and reminder flows
- Layer 4 proactive intelligence and risk actions
- HR dashboard risk and trend outputs

## 2. Epic Set

| Epic ID | Epic Name | Outcome | KPI Target |
|---|---|---|---|
| MARK-EPIC-01 | Workplace Assistant Tools | Nearby, calendar, room, menu, email assistant live | >= 95% successful valid tool actions |
| MARK-EPIC-02 | Wellbeing and Reminder Engine | Daily check-ins and reminder automation | >= 70% reminder completion rate |
| MARK-EPIC-03 | Proactive Automation Rules | Break, silence, sentiment, weekly summary | >= 90% rule evaluation reliability |
| MARK-EPIC-04 | Intelligence and Risk Scoring | Burnout, attrition, silence risk snapshots | >= 75% precision on high-risk cohort |
| MARK-EPIC-05 | HR Dashboard Intelligence Views | KPI, alerts, trends, employee risk table | Dashboard freshness under 15 minutes |

## 3. Story Backlog

## MARK-EPIC-01 Workplace Assistant Tools

| Story ID | Story | Points | Priority | Dependency |
|---|---|---:|---|---|
| MARK-US-101 | Implement nearby services search API and provider adapter | 8 | High | None |
| MARK-US-102 | Implement calendar availability endpoint with conflict scoring | 8 | High | MARK-US-101 |
| MARK-US-103 | Implement calendar event scheduling with idempotency and retries | 5 | High | MARK-US-102 |
| MARK-US-104 | Implement room availability lookup and alternatives ranking | 5 | High | MARK-US-102 |
| MARK-US-105 | Implement room booking endpoint with overlap prevention | 8 | High | MARK-US-104 |
| MARK-US-106 | Implement cafeteria menu endpoint (today/date) | 3 | Medium | None |
| MARK-US-107 | Implement structured email draft endpoint with tone controls | 5 | Medium | None |

Acceptance criteria:

- Every integration endpoint returns a normalized success/error envelope.
- External provider failures return retryable error metadata, not generic 500 responses.
- At least one integration provider can be swapped via configuration without code changes.

## MARK-EPIC-02 Wellbeing and Reminder Engine

| Story ID | Story | Points | Priority | Dependency |
|---|---|---:|---|---|
| MARK-US-201 | Create reminder schedules table and CRUD APIs | 5 | High | None |
| MARK-US-202 | Build reminder scheduler worker with timezone support | 8 | High | MARK-US-201 |
| MARK-US-203 | Add daily friendly check-in trigger and copy variants | 3 | Medium | MARK-US-202 |
| MARK-US-204 | Add medicine reminder flow in chat and acknowledgment capture | 5 | High | MARK-US-201 |
| MARK-US-205 | Add meeting reminder bridge from calendar events | 5 | Medium | MARK-US-103 |
| MARK-US-206 | Create user preference controls for reminder frequency | 5 | Medium | MARK-US-201 |

Acceptance criteria:

- Reminder scheduling supports one-time, daily, weekly, and cron-like recurrences.
- Reminder jobs are idempotent and do not duplicate notifications on worker restarts.
- Users can pause or cancel reminders without deleting history.

## MARK-EPIC-03 Proactive Automation Rules

| Story ID | Story | Points | Priority | Dependency |
|---|---|---:|---|---|
| MARK-US-301 | Implement break reminder rule using activity window tracking | 5 | High | MARK-US-201 |
| MARK-US-302 | Implement silent-employee nudge rule by inactivity thresholds | 8 | High | MARK-US-301 |
| MARK-US-303 | Implement negative sentiment escalation rule to HR alerts | 8 | High | MARK-US-401 |
| MARK-US-304 | Implement weekly HR summary generation and dispatch | 5 | High | MARK-US-501 |
| MARK-US-305 | Persist automation action audit logs with status and failures | 3 | High | MARK-US-301 |
| MARK-US-306 | Add automation policy controls per department | 5 | Medium | MARK-US-305 |

Acceptance criteria:

- Rule outcomes are traceable end-to-end (trigger, decision, action, status).
- HR escalation obeys policy gates and role-based visibility.
- Weekly summary contains top issues, risk cohort, and engagement trend deltas.

## MARK-EPIC-04 Intelligence and Risk Scoring

| Story ID | Story | Points | Priority | Dependency |
|---|---|---:|---|---|
| MARK-US-401 | Add wellbeing signals table and ingest pipeline from chat sentiment | 8 | High | None |
| MARK-US-402 | Build risk snapshot batch job (engagement, burnout, attrition, silence) | 8 | High | MARK-US-401 |
| MARK-US-403 | Add explainable risk reasons and recommendations generation | 5 | High | MARK-US-402 |
| MARK-US-404 | Add confidence scoring and calibration metrics for risk outputs | 5 | Medium | MARK-US-402 |
| MARK-US-405 | Implement high-risk cohort API for HR dashboard | 5 | High | MARK-US-402 |

Acceptance criteria:

- Risk snapshots are computed per user with explicit period ranges.
- Each high-risk result includes reason codes and confidence.
- Risk API latency remains under 2 seconds for paginated dashboard queries.

## MARK-EPIC-05 HR Dashboard Intelligence Views

| Story ID | Story | Points | Priority | Dependency |
|---|---|---:|---|---|
| MARK-US-501 | Add dashboard API: engagement, mood, activity overview | 5 | High | MARK-US-402 |
| MARK-US-502 | Add dashboard API: alerts panel and unresolved complaints | 5 | High | MARK-US-303 |
| MARK-US-503 | Add dashboard API: department sentiment and issue trends | 8 | High | MARK-US-401 |
| MARK-US-504 | Add employee risk table API (name, mood, risk, tickets, last active) | 8 | High | MARK-US-405 |
| MARK-US-505 | Implement dashboard frontend cards, charts, and risk table views | 8 | High | MARK-US-501 |
| MARK-US-506 | Add CSV export for filtered HR intelligence views | 3 | Medium | MARK-US-505 |

Acceptance criteria:

- Dashboard supports role-safe filtering by department, manager, and date range.
- Employee table supports sorting by risk and recent activity.
- Weekly quality metrics remain visible alongside new intelligence panels.

## 4. Sprint Plan (Recommended)

| Sprint | Focus | Stories |
|---|---|---|
| Sprint 9 | Foundations for proactive execution | MARK-US-101, MARK-US-102, MARK-US-201, MARK-US-401 |
| Sprint 10 | Actionable assistant tools and reminders | MARK-US-103, MARK-US-104, MARK-US-105, MARK-US-202, MARK-US-204 |
| Sprint 11 | Proactive rules and risk scoring | MARK-US-301, MARK-US-302, MARK-US-303, MARK-US-402, MARK-US-403 |
| Sprint 12 | Dashboard intelligence and hardening | MARK-US-304, MARK-US-501, MARK-US-502, MARK-US-503, MARK-US-504, MARK-US-505 |

## 5. Definition of Ready (DoR)

- API contract references are linked.
- Data model changes are reviewed.
- Observability and alerting impact is defined.
- Security and privacy checks are identified.

## 6. Definition of Done (DoD)

- Feature merged with tests (unit + integration where applicable).
- Metrics and logs are emitted and visible in dashboards.
- Backward compatibility verified for existing chat and analytics APIs.
- Documentation updated in product, API, and migration artifacts.
