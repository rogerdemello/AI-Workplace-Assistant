# MARK Proactive Data Model
## Database Migration Plan

Version: 1.0  
Date: April 13, 2026

## 1. Purpose

Add production-ready data structures required for:

- Proactive reminders
- Wellbeing signal tracking
- Periodic risk snapshots
- Automation decision/audit trails

## 2. Migration Artifact

- SQL migration file: backend/migrations/add_mark_proactive_signal_tables.sql

## 3. Tables Introduced

- activity_events
- reminder_schedules
- wellbeing_signals
- risk_snapshots
- automation_actions

## 4. Pre-Migration Checklist

1. Confirm backup/snapshot completed for production database.
2. Confirm extension pgcrypto is available (required for gen_random_uuid()).
3. Confirm baseline schema has users and conversations tables.
4. Run migration first in staging and capture execution time.

## 5. Forward Migration Procedure

1. Deploy backend code that is backward compatible with missing new tables.
2. Run migration during low-traffic window.
3. Validate table/index creation.
4. Enable new feature flags for reminders/automation incrementally.

Suggested command:

```sql
psql -d <database_name> -f backend/migrations/add_mark_proactive_signal_tables.sql
```

## 6. Verification Queries

```sql
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'activity_events',
    'reminder_schedules',
    'wellbeing_signals',
    'risk_snapshots',
    'automation_actions'
  )
ORDER BY tablename;
```

```sql
SELECT indexname, tablename
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN (
    'activity_events',
    'reminder_schedules',
    'wellbeing_signals',
    'risk_snapshots',
    'automation_actions'
  )
ORDER BY tablename, indexname;
```

## 7. Rollout Notes

- Start with read/write disabled for automation actions in production.
- Enable reminder create/list/update first.
- Enable rule workers after initial signal ingestion is healthy.
- Monitor DB growth for activity_events and automation_actions.

## 8. Rollback Strategy

If rollback is required before production writes begin, drop newly created tables in reverse dependency order:

1. automation_actions
2. risk_snapshots
3. wellbeing_signals
4. reminder_schedules
5. activity_events

Rollback should only be executed after confirming no critical production data was written to these tables.

## 9. Post-Migration Operational Tasks

1. Add retention policy for activity_events and automation_actions.
2. Add scheduled archive/partition plan when volume grows.
3. Add dashboard monitoring for failed automation actions.
4. Add alert on reminder worker lag.
