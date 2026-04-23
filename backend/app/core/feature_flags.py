"""Runtime feature flags for progressive rollout of backend capabilities."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class FeatureFlags:
    enable_rag: bool
    enable_proactive: bool
    enable_event_bus: bool
    enable_analytics_events: bool
    enable_ticket_bulk_actions: bool


@lru_cache
def get_feature_flags() -> FeatureFlags:
    """Load feature flags once per process.

    Defaults are intentionally enabled to preserve current behavior while
    still allowing quick rollback via environment variables.
    """
    return FeatureFlags(
        enable_rag=_env_bool("ENABLE_RAG", True),
        enable_proactive=_env_bool("ENABLE_PROACTIVE", True),
        enable_event_bus=_env_bool("ENABLE_EVENT_BUS", True),
        enable_analytics_events=_env_bool("ENABLE_ANALYTICS_EVENTS", True),
        enable_ticket_bulk_actions=_env_bool("ENABLE_TICKET_BULK_ACTIONS", True),
    )
