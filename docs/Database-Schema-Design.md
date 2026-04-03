# AI Workplace Assistant
## Database Schema Design (Production-Ready)

Version: 1.0  
Date: March 27, 2026

## 1. Database Stack
| Type | Technology |
|---|---|
| Relational DB | PostgreSQL |
| Vector DB | Any supported provider (configured at runtime) |
| Cache | Redis |

## 2. Delivered Artifacts
- Executable PostgreSQL schema: [db/schema.sql](../db/schema.sql)
- Architecture and functional mapping: [docs/AI-HR-Workplace-Assistant-Technical-Documentation.md](AI-HR-Workplace-Assistant-Technical-Documentation.md)

## 3. Core Design Principles
- UUID primary keys on all domain tables.
- Strong typing with PostgreSQL enums for status fields.
- Referential integrity with explicit delete behavior.
- Auditable timestamps with auto-updated updated_at triggers.
- Anonymous feedback kept fully decoupled from user identity.
- Provider registry table (`integration_providers`) drives integration selection.
- No hardcoded provider names in schema defaults.

## 4. Domain Coverage
The schema includes these bounded contexts:
- Users and organization
- Chat and conversation
- RAG document metadata and chunk references
- Ticketing and HR support workflow
- Sentiment and attrition risk
- Surveys and answer modeling
- Anonymous feedback
- Meetings and participants
- Room inventory and bookings
- Email logs and activity logs

## 5. Relationship Overview
- users -> conversations -> messages
- users -> tickets -> ticket_messages
- users -> survey_responses -> survey_answers
- users -> meetings -> meeting_participants
- rooms -> room_bookings
- documents -> document_chunks -> vector store id

## 6. Performance Optimizations
- Composite indexes for high-frequency filters and timelines.
- Partial unique indexes for survey response constraints.
- GIN index for JSONB metadata search on activity logs.
- Exclusion constraint on room bookings to prevent overlap.

## 7. Security and Compliance Considerations
- UUID identifiers avoid predictable sequential IDs.
- CITEXT enforces case-insensitive unique emails.
- Role fields designed for application RBAC enforcement.
- Anonymous feedback table intentionally has no user_id.
- Sensitive payload encryption should be enforced at application/service layer using KMS-managed keys.

## 8. Vector and Cache Design
- PostgreSQL stores chunk metadata and embedding references only.
- Embedding vectors are stored in the configured vector provider.
- Redis should cache hot policy answers, session context, and rate-limit counters.

## 9. How to Apply
Run the schema in order on a clean PostgreSQL database:

```sql
psql -d <database_name> -f db/schema.sql
```

## 10. Notes for Backend Integration
- Map enum values directly to backend constants.
- Resolve integration providers from `integration_providers` by `provider_key` and never hardcode IDs.
- Keep write operations in service layer transactions.
- Use created_at/updated_at for audit and dashboard rollups.
- Enforce tenant isolation rules in API layer if multi-tenant support is added.
