"""Time helpers for UTC-safe, database-friendly timestamps."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """Return current UTC time as a naive datetime.

    Most DB columns in this codebase are stored as naive UTC timestamps.
    This helper avoids deprecated datetime.utcnow() while keeping behavior
    compatible with existing schema expectations.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
