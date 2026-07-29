# MARK — data retention position

**Status: DRAFT. No retention is enforced today — nothing is deleted, ever.**

This document exists so that fact is visible rather than discovered during a
DPIA or a subject access request. The periods below are *proposals*; the actual
numbers are a legal and business decision, not an engineering one. What
engineering can say is what is stored, where, and what it costs to keep.

---

## Why this matters more here than in most products

MARK is designed so employees say things they would not say to their manager.
The stored consequence is a database of people's disclosures about their mental
health, their relationships with named colleagues, and their intention to leave.
Held indefinitely, that becomes a liability rather than a service — the longer
it exists, the more likely it is read by someone the employee never intended.

## What is stored

### Employee free text — highest sensitivity

| Table | Content | Notes |
|---|---|---|
| `conversations.message_text` | Everything an employee types to MARK | The core disclosure record |
| `tickets.query`, `ticket_messages` | Complaints, including anonymous ones | `is_anonymous` hides the author from HR, but `user_id` is still stored |
| `anonymous_feedback.message` | Anonymous submissions | Author intentionally not linked |
| `leave_requests.reason` | Often medical or family circumstance | |
| `employee_requests.details` | 1:1 topics, expense descriptions, document purposes | Appointment topics can be sensitive |
| `hr_alerts`, `hr_notifications` | Alert bodies quoting concerns | |
| `conversation_memory.summary` | Model-generated summaries of the above | Derived, but no less personal |
| `reminder_schedules.message` | Includes proactive nudges persisted to chat | Widened by the nudge work — see below |

### Derived signals — lower sensitivity, longer usefulness

`sentiment_logs`, `employee_scores`, `message_signals`, `risk_snapshots`,
`wellbeing_signals`, `mental_health_scores`, `mood_entries`. These are scores and
labels rather than words, and are what the HR dashboards actually read.

### Operational

`audit_logs` (stores only a SHA-256 of request bodies, never content),
`activity_events`, `automation_actions`, `webhooks`.

## Proposed periods — for the business to confirm

| Category | Proposal | Reasoning |
|---|---|---|
| Chat message text | **90 days** | Long enough for context and follow-up; short enough that a bad month is not permanent |
| Derived sentiment signals | **13 months** | Supports year-over-year trend without keeping the words |
| Tickets and their threads | **Resolution + 12 months** | Grievance records usually need a defined tail |
| Anonymous feedback | **12 months** | |
| Audit logs | **24 months** | Hashes only; the compliance argument for keeping them is stronger |
| Leave / expense / document requests | **Per finance and statutory requirements** | Not an engineering call |

Deleting chat text while keeping derived signals is the key move: HR keeps the
trends it acts on, and the employee's actual words stop existing.

## How to apply a period

Set the relevant `RETENTION_*_DAYS` (all default to 0 = keep forever), then:

```bash
cd backend
python -m scripts.apply_retention --dry-run   # always start here
python -m scripts.apply_retention --confirm
```

The script refuses to run without an explicit flag, and does nothing at all
while every period is 0. It is deliberately **not** scheduled: deletion is
irreversible and lands on employee disclosures, so it stays a decision someone
makes, having read what it is about to remove.

Expiring chat text does not disturb the dashboards — scores are computed from
`sentiment_logs`, not from the messages. Expiring `sentiment_logs` does shift
the aggregates on their next recompute, which is the intended trade.

## Known gaps to close

1. **Periods are still unset**, so nothing is deleted today. The mechanism
   exists; the numbers are a business decision.
2. **Proactive nudges now persist to chat history.** The delivery fix means
   HR decisions and check-ins are written into `conversations`. Correct for
   delivery, but it widened this surface and should be in scope.
3. **Anonymous tickets still store `user_id`.** Anonymity is enforced at the
   presentation layer — HR does not see the author. Anyone with database access
   can. Whether that is acceptable is a policy decision that should be taken
   knowingly.
4. **No subject-access or erasure path.** No endpoint or runbook exists to
   export or delete one person's data on request.
5. **No data residency position.** Deployment defaults to a single Supabase
   region; multi-region is on the Phase 4 roadmap.

## What is already sound

- Message content is never written to application logs.
- The audit trail stores body hashes, not bodies.
- Log masking covers emails, cards, and international and Indian phone numbers.
- HR-facing analytics are role-gated, and manager views exclude anonymous
  tickets and HR-only request types.
