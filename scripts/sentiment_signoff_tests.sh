#!/usr/bin/env bash
# Automated checks for sentiment and analytics readiness (pytest + frontend build).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== Backend pytest (sentiment / chat / manager analytics / RBAC) =="
cd "$ROOT/backend"
python -m pytest \
  tests/test_chat_sentiment_hr.py \
  tests/test_sentiment_api.py \
  tests/test_sentiment_service.py \
  tests/test_sentiment_llm.py \
  tests/test_sentiment_pipeline.py \
  tests/test_sentiment_source_drift_api.py \
  tests/test_manager_team_analytics.py \
  tests/test_rbac.py \
  tests/test_feedback_analytics.py \
  -q --tb=line

echo "== Frontend production build =="
cd "$ROOT/frontend"
npm run build

echo "OK: sentiment sign-off automated checks passed."
