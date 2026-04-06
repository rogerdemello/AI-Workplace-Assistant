"""Supabase client (service role — server only)."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from ..config import settings

if TYPE_CHECKING:
    from supabase import Client


def is_supabase_configured() -> bool:
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
    return bool(url and key)


@lru_cache
def get_supabase() -> "Client":
    if not is_supabase_configured():
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY "
            "(or SUPABASE_KEY)."
        )
    from supabase import create_client

    key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
    return create_client(settings.SUPABASE_URL, key)  # type: ignore[arg-type]


def supabase_or_503():
    from fastapi import HTTPException, status

    try:
        return get_supabase()
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
