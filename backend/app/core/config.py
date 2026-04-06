"""HR module settings (cached)."""

from __future__ import annotations

from functools import lru_cache

from ..config import Settings, settings as _root_settings


@lru_cache
def get_settings() -> Settings:
    return _root_settings


def supabase_url() -> str | None:
    return get_settings().SUPABASE_URL


def supabase_service_key() -> str | None:
    s = get_settings()
    return s.SUPABASE_SERVICE_KEY or s.SUPABASE_KEY
