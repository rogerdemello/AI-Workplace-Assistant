# API Contracts

This document summarizes stable response contracts for chat flow orchestration and HR analytics.

## Chat Contracts

### `POST /api/v1/chat/message`

- **Purpose**: Unified conversational entry point for employee interactions.
- **Key response fields**:
  - `response`: assistant reply text
  - `intent`: resolved turn intent
  - `flow_metadata`: structured flow progress

`flow_metadata` contract:

- `flow_name`: active flow (`ticket`, `leave_request`) or `null`
- `step`: current expected slot/question
- `missing_fields`: slots still required before completion
- `collected_fields`: slots already captured in contract state
- `completed`: true when flow action can be executed

Example:

```json
{
  "response": "Noted 2026-05-02. And what is the last day?",
  "intent": "leave_request",
  "flow_metadata": {
    "flow_name": "leave_request",
    "intent": "leave_request",
    "step": "end_date",
    "missing_fields": ["end_date", "reason"],
    "collected_fields": ["leave_type", "start_date"],
    "completed": false
  }
}
```

## Analytics Contracts

### `GET /api/v1/analytics/overview`

- **Purpose**: top-level KPI card payload.
- **Response model**: `KPIResponse`

### `GET /api/v1/analytics/sentiment`

- **Purpose**: daily sentiment breakdown for charting.
- **Response model**: `List[SentimentTrendResponse]`

### `GET /api/v1/analytics/employees`

- **Purpose**: employee risk/sentiment table.
- **Response model**: `List[EmployeeInsightResponse]`

### `GET /api/v1/analytics/dashboard`

- **Purpose**: one-call dashboard bundle for HR frontend.
- **Response model**: `DashboardBundleResponse`
- **Includes**:
  - `metrics`
  - `sentiment`
  - `employees`
  - `weekly_quality`
  - `ai_summary`
  - `manager_pattern`

## Notes for Frontend Integration

- The primary web client (`new-frontend`) calls `POST /api/v1/chat/message` with `{ message, conversation_id }` and maps `flow_metadata` to in-panel controls (select / date / yes‑no) via `new-frontend/src/lib/flow-metadata-ui.ts`.
- Treat unknown additional fields as forward-compatible.
- Depend on `flow_metadata.step` + `flow_metadata.missing_fields` for guided prompts.
- For analytics, prefer `/dashboard` for initial page load and endpoint-specific calls for partial refreshes.
