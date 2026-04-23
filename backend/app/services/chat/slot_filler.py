"""Slot filling with validation-before-state-update guarantees."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .flow_manager import FlowManager


@dataclass
class SlotFillResult:
    state: Dict[str, Any]
    errors: List[str]


def fill_slots(
    flow_manager: FlowManager,
    *,
    flow_name: str,
    state: Dict[str, Any],
    extracted_slots: Dict[str, Any],
) -> SlotFillResult:
    """Merge and validate slots before mutating contract state.

    This enforces a global invariant: invalid slots do not overwrite
    previously valid state values.
    """
    current_data = dict((state or {}).get("data") or {})
    merged, errors = flow_manager.merge_slots(flow_name, current_data, extracted_slots)

    next_state = dict(state)
    next_state["data"] = merged
    return SlotFillResult(state=next_state, errors=errors)
