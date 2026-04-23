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
