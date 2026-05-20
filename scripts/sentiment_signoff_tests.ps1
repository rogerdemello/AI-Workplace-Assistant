# Automated checks for sentiment and analytics readiness (pytest + frontend build).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "== Backend pytest (sentiment / chat / manager analytics / RBAC) =="
Set-Location (Join-Path $Root "backend")
python -m pytest `
  tests/test_chat_sentiment_hr.py `
  tests/test_sentiment_api.py `
  tests/test_sentiment_service.py `
  tests/test_sentiment_llm.py `
  tests/test_sentiment_pipeline.py `
  tests/test_sentiment_source_drift_api.py `
  tests/test_manager_team_analytics.py `
  tests/test_rbac.py `
  tests/test_feedback_analytics.py `
  -q --tb=line

Write-Host "== Frontend production build =="
Set-Location (Join-Path $Root "new-frontend")
npm run build

Write-Host "OK: sentiment sign-off automated checks passed."
