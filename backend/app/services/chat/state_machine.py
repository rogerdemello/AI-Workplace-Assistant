"""
Deterministic flow helpers — slot order, missing-slot detection, and leave input routing.

LLMs route intent; the state machine owns **order** and **validation**.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

# Strict HR leave order (questions follow first missing slot).
LEAVE_SLOT_ORDER = ("start_date", "end_date", "leave_type", "reason")

_ISO = re.compile(r"\b(20[0-9]{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01]))\b")


def _slot_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip()
        return not s or s.lower() == "unspecified"
    return False


def _date_slot_filled(value: object) -> bool:
    if _slot_empty(value):
        return False
    return bool(_ISO.search(str(value)))


def first_missing_leave_slot(data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return the next slot key to collect, in canonical order."""
    payload = data or {}
    for key in LEAVE_SLOT_ORDER:
        if key in ("start_date", "end_date"):
            if not _date_slot_filled(payload.get(key)):
                return key
            continue
        if _slot_empty(payload.get(key)):
            return key
    return None


def message_is_iso_date_only(text: str) -> bool:
    t = (text or "").strip()
    m = _ISO.fullmatch(t)
    return bool(m)


def infer_leave_patch_from_text(message: str, current_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Route a single user turn into slot updates. Dates bind to the **first missing**
    date slot in order (start → end). Does not replace the LLM extractor — complements it.
    """
    cd = dict(current_data or {})
    out: Dict[str, Any] = {}
    text = (message or "").strip()
    if not text:
        return out

    dates = _ISO.findall(text)
    if len(dates) >= 2:
        out["start_date"] = dates[0]
        out["end_date"] = dates[1]
        return out

    if len(dates) == 1 and message_is_iso_date_only(text):
        d0 = dates[0]
        if _slot_empty(cd.get("start_date")):
            out["start_date"] = d0
        elif _slot_empty(cd.get("end_date")):
            out["end_date"] = d0
        else:
            out["end_date"] = d0
        return out

    return out
