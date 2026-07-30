# MARK — staging sign-off checklist

Everything in this repo is verified by tests and a local stack. Nothing has been
run against a realistic environment. This is the list that closes that gap.

Work top to bottom; each item says what "pass" means so it cannot be waved
through.

---

## 0. Deploy correctness

- [ ] `alembic upgrade head` runs clean. **Required** — `create_all` no longer
      builds the Postgres schema.
- [ ] Boot logs show `schema_audit: schema in sync with alembic head`. An error
      here means the migration step was skipped.
- [ ] `/healthz` 200, `/readyz` reports DB, Redis and Azure OpenAI all healthy.
- [ ] `DB_CREATE_ALL` is unset or false.
- [ ] `SECRET_KEY` is a generated value, not the repo placeholder. The app will
      not boot otherwise — if it started, this passed.
- [ ] `POST /api/v1/demo/login` returns **404**. Any other status means
      `ENABLE_DEMO_LOGIN` is on and anyone can mint an HR token.

## 1. The core loop actually works

- [ ] An employee sends a chat message and gets a real model reply (not the
      "can't reach my language service" fallback — that means Azure is
      misconfigured).
- [ ] `sentiment_logs` gains a row for that message.
- [ ] The employee's `employee_scores` row updates.
- [ ] HR's Pulse and Employees screens reflect the change. **Record the delay**
      — the pipeline is deferred by default, so a lag is expected and should be
      written down rather than treated as a bug.
- [ ] `/metrics` shows `sentiment_pipeline_processed_total` climbing and
      `sentiment_pipeline_failures_total` flat.

## 2. Proactive check-ins reach people

This is the feature most likely to look fine and do nothing.

- [ ] Force `check_silent_users` and confirm a `reminder_schedules` row with
      `status = 'active'` (not `cancelled` — that was the original bug).
- [ ] Let the dispatcher run; confirm the nudge appears in the employee's chat.
- [ ] With the employee's browser **closed**, have HR approve a request, then
      open the chat: the decision must be waiting. This is the path that has
      broken three separate ways.

## 3. Confidentiality — verify with real accounts

- [ ] A manager cannot see a direct report's HR appointment or document request.
- [ ] An anonymous ticket does not raise the reporter's `open_tickets` count on
      the manager's team view.
- [ ] An employee cannot reach any `/analytics/*` route.
- [ ] `POST /tickets/sla-scan/trigger` returns 403 for a non-HR session.

## 4. Load

- [ ] `python -m scripts.loadtest --base-url <staging> --employees 25 --hr 5
      --duration 60`
- [ ] **Agree a p95 target before running.** There is no budget defined, so
      without one the numbers cannot fail and the exercise proves nothing.
- [ ] Zero errors. `/metrics` HTTP error counters flat afterwards.

## 5. Data handling

- [ ] Application logs contain no message content and no unmasked contact
      details (grep a sample for `@` and for digit runs).
- [ ] Confirm the retention position in `DATA_RETENTION.md` has been read and
      the periods decided. **Nothing is deleted today.**

## 6. Product decisions to confirm before real employees use it

- [ ] Managers can see per-report sentiment and attrition risk derived from
      private conversations. Intended, per task.txt D — needs a conscious yes.
- [ ] Anonymous tickets still store `user_id`; anonymity is enforced in the
      presentation layer only.
- [ ] HR has read `HR_METRICS.md`, particularly that these scores are not
      performance measures and silence inflates risk.

---

## Sign-off

| | Name | Date |
|---|---|---|
| Engineering | | |
| HR / People Ops | | |
| Data protection | | |
