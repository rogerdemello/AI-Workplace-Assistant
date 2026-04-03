# AI Workplace Assistant
## Jira-Ready Epics, Stories, and Backlog

Version: 1.0  
Date: March 27, 2026

## 1. Epic List
| Epic ID | Epic Name | Objective | Success Metric |
|---|---|---|---|
| EPIC-01 | Platform Foundation | Establish secure, deployable baseline | Staging deployment stable |
| EPIC-02 | Conversational Core | Deliver HR assistant chat and orchestration | P95 response < 5s |
| EPIC-03 | RAG Knowledge System | Ground answers in policy documents | Top-3 recall >= 85% |
| EPIC-04 | HR Automation & Ticketing | Resolve routine HR issues and escalate reliably | >= 80% auto-resolution |
| EPIC-05 | Employee Insight | Sentiment, surveys, and anonymous feedback | Sentiment F1 >= 0.78 |
| EPIC-06 | Productivity Integrations | Calendar and room booking support | >= 95% successful valid bookings |
| EPIC-07 | Analytics & Risk Signals | KPI dashboard and attrition alerts | Dashboard accuracy validated |
| EPIC-08 | Security, Quality, and Launch | Hardening, UAT, and production readiness | Go-live signoff complete |

## 2. Story Backlog

## EPIC-01 Platform Foundation
| Story ID | Title | Description | Points | Priority | Dependency |
|---|---|---|---:|---|---|
| US-001 | Set up mono-repo and standards | Initialize backend/frontend structure, lint, formatter, PR templates | 3 | High | None |
| US-002 | CI pipeline | Build/test workflow on pull requests | 5 | High | US-001 |
| US-003 | CD pipeline to staging | Deploy services to staging cluster | 8 | High | US-002 |
| US-004 | Provision data stores | PostgreSQL, Redis, vector DB with secrets management | 5 | High | None |
| US-005 | Auth baseline | JWT auth, RBAC roles, token refresh | 8 | High | US-001 |
| US-006 | Observability baseline | Structured logging, metrics, tracing, alert hooks | 5 | Medium | US-003 |

## EPIC-02 Conversational Core
| Story ID | Title | Description | Points | Priority | Dependency |
|---|---|---|---:|---|---|
| US-101 | Chat session APIs | Create/start/end conversation and context APIs | 5 | High | US-005 |
| US-102 | Intent classification service | Detect top HR intents and confidence score | 8 | High | US-101 |
| US-103 | Prompt orchestration | Role-aware, policy-safe prompt templates | 5 | High | US-102 |
| US-104 | Clarification flow | Ask follow-up when confidence low | 3 | High | US-102 |
| US-105 | Channel adapter: web | Connect web client chat stream to backend | 5 | High | US-101 |

## EPIC-03 RAG Knowledge System
| Story ID | Title | Description | Points | Priority | Dependency |
|---|---|---|---:|---|---|
| US-201 | Document ingestion pipeline | Upload and parse PDF/DOCX policies | 8 | High | US-004 |
| US-202 | Chunking and embeddings | Create chunks and vectors with metadata | 8 | High | US-201 |
| US-203 | Retrieval service | Similarity search and top-k context retrieval | 5 | High | US-202 |
| US-204 | Citation support | Return source references with responses | 3 | High | US-203 |
| US-205 | Document versioning controls | Active/inactive policy versions and approval status | 5 | Medium | US-201 |

## EPIC-04 HR Automation & Ticketing
| Story ID | Title | Description | Points | Priority | Dependency |
|---|---|---|---:|---|---|
| US-301 | Leave balance workflow | Leave balance query and response template | 5 | High | US-101 |
| US-302 | FAQ automation flow | Policy/benefits/payroll FAQ handler | 8 | High | US-203 |
| US-303 | Low-confidence fallback | Create ticket when confidence below threshold | 5 | High | US-302 |
| US-304 | Ticket lifecycle API | Create, assign, escalate, close ticket APIs | 8 | High | US-303 |
| US-305 | SLA rules engine | Category and severity-based SLA logic | 5 | Medium | US-304 |
| US-306 | Email drafting module | Draft leave/follow-up/complaint emails | 5 | Medium | US-103 |

## EPIC-05 Employee Insight
| Story ID | Title | Description | Points | Priority | Dependency |
|---|---|---|---:|---|---|
| US-401 | Sentiment scoring | Score chat/survey text positive/neutral/negative | 8 | High | US-101 |
| US-402 | Pulse survey module | Survey creation, scheduling, and reminders | 8 | High | US-101 |
| US-403 | Lifecycle survey templates | Onboarding/probation/exit templates | 5 | Medium | US-402 |
| US-404 | Anonymous feedback API | Private feedback channel with masking | 8 | High | US-005 |
| US-405 | HR risk alerts | Trigger alerts for trend deterioration | 5 | Medium | US-401 |
| US-406 | Attrition prototype model | Baseline risk signal generation | 8 | Medium | US-401 |

## EPIC-06 Productivity Integrations
| Story ID | Title | Description | Points | Priority | Dependency |
|---|---|---|---:|---|---|
| US-501 | Primary calendar provider adapter | OAuth and event create/read integration via provider registry | 8 | High | US-005 |
| US-502 | Secondary calendar provider adapter | Add additional calendar provider using same adapter contract | 8 | High | US-005 |
| US-503 | Availability and conflicts | Check free/busy and suggest alternatives | 5 | High | US-501 |
| US-504 | Meeting room inventory sync | Sync rooms, capacity, facilities | 5 | Medium | US-004 |
| US-505 | Room booking API | Reserve room with conflict prevention | 8 | High | US-504 |
| US-506 | Booking notifications | Confirmations, reminders, updates | 3 | Medium | US-505 |

## EPIC-07 Analytics & Risk Signals
| Story ID | Title | Description | Points | Priority | Dependency |
|---|---|---|---:|---|---|
| US-601 | KPI aggregation jobs | Resolution rate, SLA, sentiment trends | 8 | High | US-304 |
| US-602 | Dashboard APIs | Query endpoints with filters and pagination | 5 | High | US-601 |
| US-603 | Admin dashboard UI | HR/Admin UI views and filters | 8 | High | US-602 |
| US-604 | Attrition signal panel | Display risk levels and reasons | 5 | Medium | US-406 |
| US-605 | Data quality checks | Validate analytics consistency and freshness | 3 | Medium | US-601 |

## EPIC-08 Security, Quality, and Launch
| Story ID | Title | Description | Points | Priority | Dependency |
|---|---|---|---:|---|---|
| US-701 | API security hardening | Rate limiting, abuse controls, secure headers | 5 | High | US-602 |
| US-702 | Test automation suite | Unit, integration, and E2E smoke tests | 8 | High | US-105 |
| US-703 | Load and resilience testing | Concurrency and stress test scenarios | 5 | Medium | US-702 |
| US-704 | UAT execution | Pilot validation with HR stakeholders | 5 | High | US-603 |
| US-705 | Production runbooks | On-call guide, rollback, incident checklist | 3 | High | US-003 |
| US-706 | Go-live and hypercare | Launch support and post-release monitoring | 5 | High | US-704 |

## 3. Suggested Initial Sprint Backlog (Sprint 1)
| Story ID | Title | Points |
|---|---|---:|
| US-001 | Set up mono-repo and standards | 3 |
| US-002 | CI pipeline | 5 |
| US-004 | Provision data stores | 5 |
| US-005 | Auth baseline | 8 |
| US-006 | Observability baseline | 5 |

Total: 26 points

## 4. Labels and Workflow
- Labels: `backend`, `frontend`, `ai`, `security`, `devops`, `integration`, `analytics`
- Priority values: `P0`, `P1`, `P2`, `P3`
- Workflow: `Backlog -> Selected for Sprint -> In Progress -> Code Review -> QA -> Done`

## 5. Definition of Ready (DoR)
- Story has acceptance criteria.
- Dependencies identified.
- Design/API contract available.
- Test approach identified.

## 6. Definition of Done (DoD)
- Code merged with review approval.
- Tests passed in CI.
- Security/privacy checks complete.
- Monitoring and docs updated.
- Product acceptance criteria met.
