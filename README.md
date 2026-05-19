# AI Workplace Assistant

An AI-powered Friendly HR partner for HR automation and employee workplace support.

## Purpose
This project provides a friendly, human-like interface for employees to complete HR and office productivity tasks in one place.

## Core Outcomes
- Automate routine HR queries and workflows.
- Improve employee engagement and response speed.
- Provide proactive insight via sentiment and attrition analytics.

## Documentation
- [MARK Product and System Design](docs/Mark-Intelligent-Workplace-Agent-Product-System-Design.md)
- [MARK vs Infeedo B2B Comparison](docs/Mark-vs-Infeedo-B2B-Comparison.md)
- [MARK Jira Execution Backlog](docs/Mark-Jira-Execution-Backlog.md)
- [MARK Jira Execution Import CSV](docs/Mark-Jira-Execution-Import.csv)
- [MARK Layer-2 API Contracts](docs/Mark-Layer2-API-Contracts.yaml)
- [MARK Database Migration Plan](docs/Mark-Database-Migration-Plan.md)
- [Technical Documentation](docs/AI-HR-Workplace-Assistant-Technical-Documentation.md)
- [Database Schema Design](docs/Database-Schema-Design.md)
- [Task and Workflow Playbook](docs/Task-Workflow-Playbook.md)
- [Tasks, Milestones, and Delivery Roadmap](docs/Tasks-Milestones-Roadmap.md)
- [Jira Epics and Stories Backlog](docs/Jira-Epics-Stories-Backlog.md)
- [Jira Backlog CSV Import](docs/Jira-Backlog-Import.csv)
- [Jira Import Guide](docs/Jira-Import-Guide.md)
- [Sprint Execution Plan and Estimates](docs/Sprint-Execution-Plan-Estimates.md)
- [OpenAPI Skeleton](docs/openapi.yaml)
- [API Contracts](docs/API_CONTRACTS.md)
- [Staging sign-off — sentiment & HR analytics](docs/STAGING_SIGNOFF_SENTIMENT.md)
- [Architecture Diagrams (Mermaid)](docs/Architecture-Diagrams.md)

## Data Layer
- [PostgreSQL Production Schema](db/schema.sql)

## MVP Focus
Phase 1 prioritizes:
- Friendly HR partner experience (human-like, trusted, workflow-first)
- RAG for HR policies and FAQs
- HR ticket automation
- Email drafting assistant

## Suggested Stack
- Backend: FastAPI (Python)
- AI: GPT + RAG (LangChain or equivalent)
- Data: PostgreSQL + Vector DB + Redis
- Frontend: React web app + Slack/Teams bot integration
- Deployment: Docker + Kubernetes (AWS or Azure)

## Local Development
- Frontend: `new-frontend` (Vite + React + React Router)
- Backend: `backend` (FastAPI)

```bash
# Backend
cd backend && python -m uvicorn app.main:app --reload

# Frontend
cd new-frontend && npm install && npm run dev
```

### Seeded accounts (FastAPI)
Run from `backend`: `python -m scripts.seed_dummy_users`

| Role      | Email                  | Password     |
|-----------|-------------------------|--------------|
| HR        | `hr1@infeedo.ai`        | `password123` |
| Manager   | `manager1@infeedo.ai`   | `password123` |
| Employee  | `employee1@infeedo.ai`  | `password123` |

`employee1` is linked to **`manager1`** as direct manager and to a **`General`** department so manager dashboards have data after seed.

### End-to-end smoke (optional)
With API running (`uvicorn`) and DB seeded:

```bash
cd backend
python -m scripts.smoke_e2e
```

Override base URL if needed: `SMOKE_API_URL=http://localhost:8000 python -m scripts.smoke_e2e`

Use **real** `AZURE_OPENAI_*` values in `.env` for LLM-backed chat and hybrid sentiment (not mock keys).

Run the app with Docker Compose:

```bash
docker compose up --build
```

This starts:
- Backend API on `http://localhost:8000`
- Primary frontend (`new-frontend`) on `http://localhost:8080`
