# Staging sign-off — sentiment → HR / manager analytics

Use this before calling the sentiment milestone **production-ready**. Replace placeholders with your environment values.

## Preconditions

- [ ] Backend deployed with latest migrations (includes `sentiment_logs.analysis_source` if you run Alembic).
- [ ] `.env` reflects intent: `SENTIMENT_HYBRID_ENABLED`, Azure keys if using LLM path, sustained-risk thresholds as desired.
- [ ] HR and employee test accounts available (roles verified).

## Automated pre-check (local / CI)

Run from the **repository root** (re-run anytime before or after staging):

**Bash (Git Bash / macOS / Linux)**

```bash
bash scripts/sentiment_signoff_tests.sh
```

**PowerShell**

```powershell
.\scripts\sentiment_signoff_tests.ps1
```

**Manual equivalent**

```bash
cd backend && python -m pytest \
  tests/test_chat_sentiment_hr.py tests/test_sentiment_api.py tests/test_sentiment_service.py \
  tests/test_sentiment_llm.py tests/test_sentiment_pipeline.py tests/test_sentiment_source_drift_api.py \
  tests/test_manager_team_analytics.py tests/test_rbac.py tests/test_feedback_analytics.py -q --tb=line
cd ../new-frontend && npm run build
```

## 1. Chat → database

- [ ] As **employee**, send **≥3** clearly negative messages in chat (or use unified `/api/v1/chat/message` if UI unavailable).
- [ ] Confirm rows in **`sentiment_logs`** for that user (`employee_id`, `label`, `score`, **`analysis_source`** where applicable).
- [ ] Confirm **`employee_scores`** updates for that user (`sentiment_score`, `risk_score`, `trend_label`).

## 2. HR — Pulse / APIs

- [ ] As **HR**, open Pulse (or `GET /api/v1/analytics/dashboard?drift_days=7`): bundle loads; **sentiment_source_drift** present when logs exist.
- [ ] **Classifier mix** card shows non-zero totals when traffic exists; **timeseries** charts load (`classifier_source_trend` / emotions).
- [ ] **People spotlight** shows freshness / confidence / sustained-risk badges where data supports them.
- [ ] **`GET /api/v1/analytics/sentiment/source-drift`** and **`.../timeseries`** return **200** for HR; **403** as employee (spot-check).

## 3. Sustained-risk alerting

- [ ] With **≥ configured minimum** negative logs in the sustained window, **`hr_notifications`** contains **`sustained_sentiment_risk`** (dedupe respected within cooldown).
- [ ] HR inbox / portal lists the notification (if product surfaces `hr_notifications`).

## 4. Manager scope

- [ ] As **manager**, Manager page: emotion + **classifier** trends load.
- [ ] Data reflects **direct reports only** (spot-check: non-report employee logs should not move manager-only series).

## 5. Regression quick checks

- [ ] Employee **cannot** access HR analytics routes (**403**).
- [ ] **`scripts/sentiment_signoff_tests.sh`** (or `.ps1`) passes — same scope as `test_chat_sentiment_hr`, `test_sentiment_*`, `test_manager_team_analytics`, RBAC, feedback analytics.

## Sign-off

| Role   | Name | Date | Notes |
|--------|------|------|-------|
| Owner  |      |      |       |

---

*Optional later: load test chat + analytics, structured metrics for pipeline latency/errors, HR one-pager mapping screens to APIs (`task.txt`).*
