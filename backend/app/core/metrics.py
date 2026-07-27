"""In-process metrics for pipeline health and API errors.

Deliberately dependency-free: the stack has no Prometheus client, and adding one
for a handful of counters isn't worth the deploy surface. This keeps bounded
counters and latency summaries in memory, exposed via ``/metrics`` for scraping
or eyeballing during an incident.

Scope and limits, so nobody reads more into these numbers than they carry:
  * Per-process. With multiple workers each has its own view; treat values as a
    sample, not a cluster total.
  * Reset on restart. Use them for "is it happening now", not for history.
  * Latency is count/sum/max, not percentiles — enough to spot a regression.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Dict, Optional

_lock = threading.Lock()
_counters: Dict[str, int] = defaultdict(int)
_latency: Dict[str, Dict[str, float]] = {}

#: Guards against unbounded growth if a caller ever derives a label from
#: user input — a metric name explosion would be a slow memory leak.
_MAX_SERIES = 500


def _labelled(name: str, labels: Optional[Dict[str, str]]) -> str:
    if not labels:
        return name
    suffix = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    return f"{name}{{{suffix}}}"


def increment(name: str, labels: Optional[Dict[str, str]] = None, amount: int = 1) -> None:
    """Bump a counter. Never raises — metrics must not break the request path."""
    try:
        key = _labelled(name, labels)
        with _lock:
            if key not in _counters and len(_counters) >= _MAX_SERIES:
                return
            _counters[key] += amount
    except Exception:
        pass


def observe_latency(name: str, seconds: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Record a duration. Never raises."""
    try:
        key = _labelled(name, labels)
        with _lock:
            entry = _latency.get(key)
            if entry is None:
                if len(_latency) >= _MAX_SERIES:
                    return
                entry = {"count": 0.0, "sum_seconds": 0.0, "max_seconds": 0.0}
                _latency[key] = entry
            entry["count"] += 1
            entry["sum_seconds"] += seconds
            entry["max_seconds"] = max(entry["max_seconds"], seconds)
    except Exception:
        pass


def snapshot() -> Dict[str, Any]:
    """Current values. Safe to call at any time."""
    with _lock:
        latency = {
            key: {
                "count": int(entry["count"]),
                "avg_seconds": round(entry["sum_seconds"] / entry["count"], 4)
                if entry["count"]
                else 0.0,
                "max_seconds": round(entry["max_seconds"], 4),
            }
            for key, entry in _latency.items()
        }
        return {"counters": dict(_counters), "latency": latency}


def reset() -> None:
    """Clear all series. For tests."""
    with _lock:
        _counters.clear()
        _latency.clear()
