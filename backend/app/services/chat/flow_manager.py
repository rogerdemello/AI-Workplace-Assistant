"""Centralized flow definitions and state contract manager for chat orchestration."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from .contracts import FlowStateContract
from .flows import (
    appointment_flow,
    document_flow,
    expense_flow,
    leave_flow,
    policy_flow,
    shift_change_flow,
    ticket_flow,
)


class FlowValidationError(ValueError):
    pass


def _slot_value_missing(value: object) -> bool:
    """Treat placeholder replies as empty for flow progression."""
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip()
        return not s or s.lower() == "unspecified"
    return False


#: Slots that must coerce to a calendar date, per flow.
_DATE_SLOTS: Dict[str, set[str]] = {
    leave_flow.FLOW_NAME: {"start_date", "end_date"},
    shift_change_flow.FLOW_NAME: {"start_date", "end_date"},
    appointment_flow.FLOW_NAME: {"preferred_date"},
    expense_flow.FLOW_NAME: {"expense_date"},
}

_TIME_PATTERNS = (
    re.compile(r"^(?P<h>\d{1,2}):(?P<m>\d{2})\s*(?P<mer>am|pm)?$", re.IGNORECASE),
    re.compile(r"^(?P<h>\d{1,2})\s*(?P<mer>am|pm)$", re.IGNORECASE),
)


def coerce_time(value: Any) -> Optional[str]:
    """Normalize '3pm', '15:00', '11:30 AM' to 24-hour HH:MM. None when unreadable."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower() == "unspecified":
        return None
    for pattern in _TIME_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        hour = int(match.group("h"))
        minute = int(match.groupdict().get("m") or 0)
        meridiem = (match.groupdict().get("mer") or "").lower()
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    return None


def coerce_amount(value: Any) -> Optional[float]:
    """Pull a positive money value out of '2500', '₹2,500.50', 'about 900 rupees'."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if value > 0 else None
    if not isinstance(value, str):
        return None
    match = re.search(r"\d[\d,]*(?:\.\d+)?", value)
    if not match:
        return None
    try:
        amount = float(match.group(0).replace(",", ""))
    except ValueError:
        return None
    return amount if amount > 0 else None


class FlowManager:
    INTENT_TO_FLOW = {
        "ticket_create": ticket_flow.FLOW_NAME,
        "complaint": ticket_flow.FLOW_NAME,
        "leave_request": leave_flow.FLOW_NAME,
        "policy_query": policy_flow.FLOW_NAME,
        "benefits_question": policy_flow.FLOW_NAME,
        "appointment_request": appointment_flow.FLOW_NAME,
        "expense_claim": expense_flow.FLOW_NAME,
        "shift_change_request": shift_change_flow.FLOW_NAME,
        "document_request": document_flow.FLOW_NAME,
    }

    #: Flows that collect slots and end in a confirm step. The orchestrator drives
    #: these through the generic slot loop rather than a bespoke branch.
    SLOT_FLOWS = (
        appointment_flow.FLOW_NAME,
        expense_flow.FLOW_NAME,
        shift_change_flow.FLOW_NAME,
        document_flow.FLOW_NAME,
    )

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
            **{
                module.FLOW_NAME: {
                    "required_fields": list(module.required_fields),
                    "steps": list(module.steps),
                    "prompts": dict(module.prompts),
                }
                for module in (appointment_flow, expense_flow, shift_change_flow, document_flow)
            },
        }

    def flow_for_intent(self, intent: Optional[str]) -> Optional[str]:
        if not intent:
            return None
        return self.INTENT_TO_FLOW.get(intent)

    def required_fields(self, flow_name: str) -> list[str]:
        return list(self._definitions.get(flow_name, {}).get("required_fields", []))

    def missing_fields(self, flow_name: str, data: Optional[Dict[str, Any]]) -> list[str]:
        payload = data or {}
        missing: list[str] = []
        for field in self.required_fields(flow_name):
            value = payload.get(field)
            if value is None:
                missing.append(field)
                continue
            if isinstance(value, str):
                if not value.strip() or value.strip().lower() == "unspecified":
                    missing.append(field)
                    continue
            if field in _DATE_SLOTS.get(flow_name, set()) and isinstance(payload.get(field), str):
                if self._coerce_date(payload.get(field)) is None:
                    missing.append(field)
                    continue
            if field == "preferred_time" and coerce_time(payload.get(field)) is None:
                missing.append(field)
                continue
            if field == "amount" and coerce_amount(payload.get(field)) is None:
                missing.append(field)
        return missing

    def ensure_state_contract(
        self,
        state: Optional[Dict[str, Any]],
        *,
        intent: str,
    ) -> Dict[str, Any]:
        return FlowStateContract.from_state(state, intent=intent).model_dump()

    def prompt_for_step(self, flow_name: str, step: str, data: Optional[Dict[str, Any]] = None) -> str:
        """Return the prompt for the given step, but check if step is already filled."""
        prompts = self._definitions.get(flow_name, {}).get("prompts", {})
        d = data or {}
        
        # CRITICAL FIX: If the step's slot is already filled, don't ask again - move to next step
        if flow_name == leave_flow.FLOW_NAME:
            if step == "start_date" and not self._missing_leave_date(d, "start_date"):
                # Start date already filled, skip to end date
                if self._missing_leave_date(d, "end_date"):
                    start = d.get("start_date", "")
                    return f"Noted {start}. What end date works?"
            if step == "end_date" and not self._missing_leave_date(d, "end_date"):
                # End date already filled, skip to leave type
                return prompts.get("leave_type", "What type of leave is this?")
            if step == "leave_type" and not _slot_value_missing(d.get("leave_type")):
                # Leave type already filled, skip to reason
                return prompts.get("reason", "What's the reason for your leave?")
            if step == "reason" and not _slot_value_missing(d.get("reason")):
                # Reason already filled, skip to confirm
                return self._build_leave_confirm_prompt(d)
            if step == "end_date":
                start = d.get("start_date", "")
                return f"Noted {start}. What end date works?"
            if step == "end_date_invalid":
                return "That end date looks earlier than the start date. What's the correct end date?"
            if step == "max_duration_exceeded":
                return "Leave requests can't exceed 60 days. Could you adjust the dates?"
            if step == "start_date_invalid":
                return "Start dates can't be more than 1 day in the past. Please use today or a future date."
            if step == "confirm":
                return self._build_leave_confirm_prompt(d)
        
        if flow_name == ticket_flow.FLOW_NAME and step == "confirm":
            return self._build_ticket_confirm_prompt(d)

        if flow_name in self.SLOT_FLOWS and step == "confirm":
            return self._build_slot_confirm_prompt(flow_name, d)

        return prompts.get(step, "Got it. Let me process that.")

    #: Human labels for the confirm summary, per flow.
    _CONFIRM_LABELS: Dict[str, Dict[str, str]] = {
        appointment_flow.FLOW_NAME: {
            "topic": "About",
            "preferred_date": "Date",
            "preferred_time": "Time",
            "mode": "Mode",
        },
        expense_flow.FLOW_NAME: {
            "expense_type": "Type",
            "amount": "Amount",
            "expense_date": "Date",
            "description": "For",
        },
        shift_change_flow.FLOW_NAME: {
            "change_type": "Request",
            "start_date": "From",
            "end_date": "To",
            "reason": "Reason",
        },
        document_flow.FLOW_NAME: {
            "document_type": "Document",
            "purpose": "Purpose",
        },
    }

    _CONFIRM_HEADERS: Dict[str, str] = {
        appointment_flow.FLOW_NAME: "Want me to send this to HR?",
        expense_flow.FLOW_NAME: "Want me to submit this claim?",
        shift_change_flow.FLOW_NAME: "Want me to send this to your manager and HR?",
        document_flow.FLOW_NAME: "Want me to request this from HR?",
    }

    def _build_slot_confirm_prompt(self, flow_name: str, data: Dict[str, Any]) -> str:
        """Echo the collected slots back before the flow writes anything."""
        labels = self._CONFIRM_LABELS.get(flow_name, {})
        parts = [self._CONFIRM_HEADERS.get(flow_name, "Ready to submit this?")]
        for field, label in labels.items():
            value = data.get(field)
            if _slot_value_missing(value):
                continue
            parts.append(f"{label}: {value}")
        parts.append("Say yes to confirm or no to make changes.")
        return " ".join(parts)
    
    def _build_leave_confirm_prompt(self, data: Dict[str, Any]) -> str:
        """Build confirmation prompt for leave request with collected data."""
        start = data.get("start_date", "")
        end = data.get("end_date", "")
        leave_type = data.get("leave_type", "")
        reason = data.get("reason", "")
        
        parts = [f"Want me to submit this leave request?"]
        if start and end:
            parts.append(f"From {start} to {end}")
        if leave_type:
            parts.append(f"Type: {leave_type}")
        if reason:
            parts.append(f"Reason: {reason}")
        parts.append("Say yes to confirm or no to make changes.")
        return " ".join(parts)
    
    def _build_ticket_confirm_prompt(self, data: Dict[str, Any]) -> str:
        """Build confirmation prompt for ticket with collected data."""
        issue = data.get("issue", "")
        dept = data.get("department", "")
        anonymous = data.get("anonymous")
        
        parts = [f"Ready to send this to HR?"]
        if issue:
            parts.append(f"Issue: {issue}")
        if dept:
            parts.append(f"Department: {dept}")
        if anonymous is not None:
            parts.append("Anonymous" if anonymous else "Not anonymous")
        parts.append("Say yes to confirm or no to make changes.")
        return " ".join(parts)

    def merge_slots(self, flow_name: str, current_data: Dict[str, Any], extracted_data: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
        merged = dict(current_data or {})
        errors: list[str] = []

        for key, value in (extracted_data or {}).items():
            if value is None:
                continue

            if key in _DATE_SLOTS.get(flow_name, set()):
                parsed = self._coerce_date(value)
                if parsed is None:
                    errors.append(f"invalid_{key}")
                    continue
                merged[key] = parsed.isoformat()
                continue

            if flow_name == appointment_flow.FLOW_NAME and key == "preferred_time":
                parsed_time = coerce_time(value)
                if parsed_time is None:
                    errors.append("invalid_preferred_time")
                    continue
                merged[key] = parsed_time
                continue

            if flow_name == expense_flow.FLOW_NAME and key == "amount":
                parsed_amount = coerce_amount(value)
                if parsed_amount is None:
                    errors.append("invalid_amount")
                    continue
                merged[key] = parsed_amount
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

        if flow_name == shift_change_flow.FLOW_NAME:
            start = self._coerce_date(merged.get("start_date"))
            end = self._coerce_date(merged.get("end_date"))
            if start and end and end < start:
                errors.append("end_before_start")
            if start and end and (end - start).days + 1 > 90:
                errors.append("max_duration_exceeded")
            if start and start < date.today() - timedelta(days=1):
                errors.append("start_date_too_far_in_past")

        if flow_name == appointment_flow.FLOW_NAME:
            preferred = self._coerce_date(merged.get("preferred_date"))
            if preferred and preferred < date.today():
                errors.append("preferred_date_in_past")

        return merged, errors

    def next_step(
        self,
        flow_name: str,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        last_question: Optional[str] = None,
    ) -> str:
        step = self._compute_next_step(flow_name, data, context)
        if step == last_question and step != "done" and self._step_has_substantive_answer(
            flow_name, data, step
        ):
            temp_data = dict(data)
            temp_data[step] = temp_data.get(step, "unspecified")
            step = self._compute_next_step(flow_name, temp_data, context)
        return step

    def _step_has_substantive_answer(self, flow_name: str, data: Dict[str, Any], step: str) -> bool:
        if flow_name == leave_flow.FLOW_NAME:
            if step in ("start_date", "end_date"):
                return not self._missing_leave_date(data, step)
            if step == "reason":
                return not _slot_value_missing(data.get("reason"))
            if step == "leave_type":
                return not _slot_value_missing(data.get("leave_type"))
            if step == "confirm":
                return True
        if flow_name == ticket_flow.FLOW_NAME:
            if step == "confirm":
                return True
        if flow_name in self.SLOT_FLOWS:
            if step == "confirm":
                return True
            if step in _DATE_SLOTS.get(flow_name, set()):
                return not self._missing_date_slot(data, step)
            if step == "preferred_time":
                return coerce_time(data.get("preferred_time")) is not None
            if step == "amount":
                return coerce_amount(data.get("amount")) is not None
            return not _slot_value_missing(data.get(step))
        return bool(data.get(step))

    def _missing_leave_date(self, data: Dict[str, Any], key: str) -> bool:
        return self._missing_date_slot(data, key)

    def _compute_next_step(self, flow_name: str, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
        if flow_name == leave_flow.FLOW_NAME:
            if self._missing_leave_date(data, "start_date"):
                return "start_date"
            if self._missing_leave_date(data, "end_date"):
                return "end_date"
            start = self._coerce_date(data.get("start_date"))
            end = self._coerce_date(data.get("end_date"))
            if start and end and end < start:
                return "end_date_invalid"
            if start and end and (end - start).days + 1 > 60:
                return "max_duration_exceeded"
            if start and start < date.today() - timedelta(days=1):
                return "start_date_invalid"
            if _slot_value_missing(data.get("leave_type")):
                return "leave_type"
            if _slot_value_missing(data.get("reason")):
                return "reason"
            return "confirm"

        if flow_name == ticket_flow.FLOW_NAME:
            if _slot_value_missing(data.get("issue")):
                return "issue"
            if _slot_value_missing(data.get("against")):
                return "against"
            if data.get("anonymous") is None:
                return "anonymous"
            return "confirm"

        if flow_name == policy_flow.FLOW_NAME:
            if not data.get("query"):
                return "query"
            return "done"

        if flow_name == appointment_flow.FLOW_NAME:
            if _slot_value_missing(data.get("topic")):
                return "topic"
            if self._missing_date_slot(data, "preferred_date"):
                return "preferred_date"
            if self._coerce_date(data.get("preferred_date")) < date.today():
                return "preferred_date_invalid"
            if _slot_value_missing(data.get("preferred_time")):
                return "preferred_time"
            if coerce_time(data.get("preferred_time")) is None:
                return "preferred_time_invalid"
            if _slot_value_missing(data.get("mode")):
                return "mode"
            return "confirm"

        if flow_name == expense_flow.FLOW_NAME:
            if _slot_value_missing(data.get("expense_type")):
                return "expense_type"
            if _slot_value_missing(data.get("amount")):
                return "amount"
            if coerce_amount(data.get("amount")) is None:
                return "amount_invalid"
            if self._missing_date_slot(data, "expense_date"):
                return "expense_date"
            if _slot_value_missing(data.get("description")):
                return "description"
            return "confirm"

        if flow_name == shift_change_flow.FLOW_NAME:
            if _slot_value_missing(data.get("change_type")):
                return "change_type"
            if self._missing_date_slot(data, "start_date"):
                return "start_date"
            if self._missing_date_slot(data, "end_date"):
                return "end_date"
            start = self._coerce_date(data.get("start_date"))
            end = self._coerce_date(data.get("end_date"))
            if end < start:
                return "end_date_invalid"
            if (end - start).days + 1 > 90:
                return "max_duration_exceeded"
            if start < date.today() - timedelta(days=1):
                return "start_date_invalid"
            if _slot_value_missing(data.get("reason")):
                return "reason"
            return "confirm"

        if flow_name == document_flow.FLOW_NAME:
            if _slot_value_missing(data.get("document_type")):
                return "document_type"
            if _slot_value_missing(data.get("purpose")):
                return "purpose"
            return "confirm"

        return "done"

    def _missing_date_slot(self, data: Dict[str, Any], key: str) -> bool:
        value = data.get(key)
        if _slot_value_missing(value):
            return True
        return self._coerce_date(value) is None

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
