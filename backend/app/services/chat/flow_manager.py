"""Centralized flow definitions and state contract manager for chat orchestration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from .flows import leave_flow, policy_flow, ticket_flow


class FlowValidationError(ValueError):
    pass


class FlowManager:
    INTENT_TO_FLOW = {
        "ticket_create": ticket_flow.FLOW_NAME,
        "complaint": ticket_flow.FLOW_NAME,
        "leave_request": leave_flow.FLOW_NAME,
        "policy_query": policy_flow.FLOW_NAME,
        "benefits_question": policy_flow.FLOW_NAME,
    }

    def __init__(self) -> None:
        self._definitions: Dict[str, Dict[str, Any]] = {
            ticket_flow.FLOW_NAME: {
                "required_fields": list(ticket_flow.required_fields),
                "steps": list(ticket_flow.steps),
                "prompts": dict(ticket_flow.prompts),
            },
            leave_flow.FLOW_NAME: {
                "required_fields": list(leave_flow.required_fields),
                "steps": list(leave_flow.steps),
                "prompts": dict(leave_flow.prompts),
            },
            policy_flow.FLOW_NAME: {
                "required_fields": list(policy_flow.required_fields),
                "steps": list(policy_flow.steps),
                "prompts": dict(policy_flow.prompts),
            },
        }

    def flow_for_intent(self, intent: Optional[str]) -> Optional[str]:
        if not intent:
            return None
        return self.INTENT_TO_FLOW.get(intent)

    def ensure_state_contract(
        self,
        state: Optional[Dict[str, Any]],
        *,
        intent: str,
    ) -> Dict[str, Any]:
        data = (state or {}).get("data")
        step = (state or {}).get("step")
        completed = bool((state or {}).get("completed", False))
        last_question = (state or {}).get("last_question")
        if not isinstance(data, dict):
            data = {}
        return {
            "intent": intent,
            "step": step,
            "data": data,
            "completed": completed,
            "last_question": last_question,
        }

    def prompt_for_step(self, flow_name: str, step: str, data: Optional[Dict[str, Any]] = None) -> str:
        prompts = self._definitions.get(flow_name, {}).get("prompts", {})
        if flow_name == leave_flow.FLOW_NAME and step == "start_date":
            leave_type = (data or {}).get("leave_type")
            if leave_type:
                return f"Got it — {leave_type}. When does it start? (YYYY-MM-DD works great)"
        if flow_name == leave_flow.FLOW_NAME and step == "end_date":
            start = (data or {}).get("start_date", "")
            return f"Noted {start}. And what is the last day?"
        if flow_name == leave_flow.FLOW_NAME and step == "end_date_invalid":
            return "That end date looks earlier than the start date. What's the correct end date?"
        if flow_name == leave_flow.FLOW_NAME and step == "max_duration_exceeded":
            return "Leave requests can't exceed 60 days. Could you adjust the dates?"
        if flow_name == leave_flow.FLOW_NAME and step == "start_date_invalid":
            return "Start dates can't be more than 1 day in the past. Please use today or a future date."
        return prompts.get(step, "Got it. Let me process that.")

    def merge_slots(self, flow_name: str, current_data: Dict[str, Any], extracted_data: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
        merged = dict(current_data or {})
        errors: list[str] = []

        for key, value in (extracted_data or {}).items():
            if value is None:
                continue

            if flow_name == leave_flow.FLOW_NAME and key in {"start_date", "end_date"}:
                parsed = self._coerce_date(value)
                if parsed is None:
                    errors.append(f"invalid_{key}")
                    continue
                merged[key] = parsed.isoformat()
                continue

            if flow_name == ticket_flow.FLOW_NAME and key == "severity":
                normalized = str(value).strip().lower()
                if normalized not in ticket_flow.allowed_severity:
                    errors.append("invalid_severity")
                    continue
                merged[key] = normalized
                continue

            if flow_name == ticket_flow.FLOW_NAME and key == "anonymous":
                if isinstance(value, bool):
                    merged[key] = value
                else:
                    errors.append("invalid_anonymous")
                continue

            merged[key] = value

        if flow_name == leave_flow.FLOW_NAME:
            start = self._coerce_date(merged.get("start_date"))
            end = self._coerce_date(merged.get("end_date"))
            if start and end and end < start:
                errors.append("end_before_start")
            if start and end and (end - start).days + 1 > 60:
                errors.append("max_duration_exceeded")
            if start and start < date.today() - timedelta(days=1):
                errors.append("start_date_too_far_in_past")

        return merged, errors

    def next_step(
        self,
        flow_name: str,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        last_question: Optional[str] = None,
    ) -> str:
        step = self._compute_next_step(flow_name, data, context)
        if step == last_question and step != "done" and data.get(step):
            temp_data = dict(data)
            temp_data[step] = temp_data.get(step, "unspecified")
            step = self._compute_next_step(flow_name, temp_data, context)
        return step

    def _compute_next_step(self, flow_name: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
        if flow_name == leave_flow.FLOW_NAME:
            if not data.get("leave_type"):
                return "leave_type"
            if not data.get("start_date"):
                return "start_date"
            if not data.get("end_date"):
                return "end_date"
            start = self._coerce_date(data.get("start_date"))
            end = self._coerce_date(data.get("end_date"))
            if start and end and end < start:
                return "end_date_invalid"
            if start and end and (end - start).days + 1 > 60:
                return "max_duration_exceeded"
            if start and start < date.today() - timedelta(days=1):
                return "start_date_invalid"
            if not data.get("reason"):
                return "reason"
            return "done"

        if flow_name == ticket_flow.FLOW_NAME:
            if not data.get("issue"):
                return "issue"
            if not data.get("severity"):
                return "severity"
            if not data.get("against"):
                return "against"
            if not data.get("department"):
                return "department"
            if data.get("anonymous") is None:
                if (context or {}).get("_anon_asked"):
                    data["anonymous"] = False
                    return "done"
                return "anonymous"
            return "done"

        if flow_name == policy_flow.FLOW_NAME:
            if not data.get("query"):
                return "query"
            return "done"

        return "done"

    def _coerce_date(self, value: Any) -> Optional[date]:
        if isinstance(value, date):
            if value.year < 2000 or value.year > 2100:
                return None
            return value

        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
                if parsed.year < 2000 or parsed.year > 2100:
                    return None
                return parsed
            except Exception:
                return None

        return None
