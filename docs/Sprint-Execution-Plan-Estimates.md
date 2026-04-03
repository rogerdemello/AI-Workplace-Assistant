# AI Workplace Assistant
## Sprint Execution Plan and Effort Estimates

Version: 1.0  
Date: March 27, 2026

## 1. Planning Assumptions
- Sprint length: 2 weeks
- Team velocity (starting): 28 to 34 story points per sprint
- Environments: development, staging, production
- Estimation scale: Fibonacci (1, 2, 3, 5, 8, 13)

## 2. Sprint-by-Sprint Plan

## Sprint 1: Foundation and Platform Readiness
Goal: Build secure baseline and delivery pipeline.

Planned stories:
- US-001 (3): Repository structure and standards
- US-002 (5): CI pipeline
- US-004 (5): Data stores provisioning
- US-005 (8): Auth baseline
- US-006 (5): Observability baseline

Committed points: 26  
Stretch: US-003 (8) CD pipeline to staging

Exit goals:
- CI green on pull requests.
- Auth working in staging.
- Basic telemetry available.

## Sprint 2: Chat and RAG Foundations
Goal: Enable first end-to-end query handling with retrieval.

Planned stories:
- US-101 (5): Chat session APIs
- US-102 (8): Intent classification
- US-201 (8): Document ingestion
- US-202 (8): Embeddings and indexing
- US-105 (5): Web chat adapter

Committed points: 34

Exit goals:
- User can ask policy question in web chat.
- Retrieval index populated from sample documents.

## Sprint 3: HR FAQ Automation and Ticket Fallback
Goal: Deliver MVP-level HR support quality and fallback.

Planned stories:
- US-203 (5): Retrieval service
- US-204 (3): Citations
- US-302 (8): FAQ automation flow
- US-303 (5): Low-confidence fallback
- US-304 (8): Ticket lifecycle API
- US-306 (5): Email drafting module

Committed points: 34

Exit goals:
- FAQ flow reaches >= 80% benchmark automation.
- Low-confidence queries create traceable tickets.

## Sprint 4: Sentiment and Survey Core
Goal: Introduce employee listening and trend visibility.

Planned stories:
- US-401 (8): Sentiment scoring
- US-402 (8): Pulse survey module
- US-403 (5): Lifecycle templates
- US-405 (5): HR risk alerts
- US-205 (5): Document versioning controls

Committed points: 31

Exit goals:
- Sentiment scoring active on chat messages.
- Survey campaigns schedulable by HR admin.

## Sprint 5: Anonymous Feedback and Risk Prototype
Goal: Build trust-safe feedback and early attrition intelligence.

Planned stories:
- US-404 (8): Anonymous feedback API
- US-406 (8): Attrition prototype model
- US-601 (8): KPI aggregation jobs
- US-602 (5): Dashboard APIs

Committed points: 29

Exit goals:
- Anonymous feedback cannot be identity-linked in HR views.
- Baseline risk indicators visible through API.

## Sprint 6: Calendar Integrations
Goal: Turn assistant into practical daily workplace helper.

Planned stories:
- US-501 (8): Primary calendar provider adapter
- US-502 (8): Secondary calendar provider adapter
- US-503 (5): Availability/conflict checks
- US-701 (5): API security hardening
- US-702 (8): Test automation suite

Committed points: 34

Exit goals:
- Meeting scheduling succeeds for valid requests.
- Integration test suite validates adapter behavior.

## Sprint 7: Room Booking and Notification Reliability
Goal: Complete productivity workflows with reliability controls.

Planned stories:
- US-504 (5): Room inventory sync
- US-505 (8): Room booking API
- US-506 (3): Booking notifications
- US-703 (5): Load/resilience testing
- US-603 (8): Admin dashboard UI (initial)

Committed points: 29

Exit goals:
- Room booking has conflict prevention.
- Core dashboard views available in staging.

## Sprint 8: Launch Hardening and Go-Live
Goal: Release readiness and controlled production launch.

Planned stories:
- US-604 (5): Attrition signal panel
- US-605 (3): Data quality checks
- US-704 (5): UAT execution
- US-705 (3): Production runbooks
- US-706 (5): Go-live and hypercare

Committed points: 21  
Reserved capacity: defect fixes and hardening

Exit goals:
- UAT signoff completed.
- Launch checklist complete.
- Production cutover approved.

## 3. Milestone Gates
- Gate 1 (End Sprint 1): Platform gate
- Gate 2 (End Sprint 3): MVP functionality gate
- Gate 3 (End Sprint 5): Insight and privacy gate
- Gate 4 (End Sprint 7): Integration gate
- Gate 5 (End Sprint 8): Production launch gate

## 4. Capacity and Risk Controls
- Keep 15% sprint capacity unallocated for bugs and integration drift.
- Enforce feature flags for incomplete modules.
- Use canary rollout in production.
- Track DORA and product KPIs in weekly review.

## 5. Weekly Tracking Template
| Metric | Target | Actual | Status |
|---|---|---|---|
| Sprint velocity | 28-34 |  |  |
| Escaped defects | <= 2 |  |  |
| API P95 latency | < 5s |  |  |
| Automation ratio | >= 80% |  |  |
| Uptime | >= 99.9% |  |  |

## 6. Dependencies to Monitor
- HRMS sandbox availability
- Calendar app approval and OAuth setup
- Data privacy/legal signoff on anonymous feedback design
- Policy document owner alignment for RAG source-of-truth
