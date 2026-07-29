from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict

from ...config import settings


def _normalize_phone_map_key(key: str) -> str:
    k = str(key).strip()
    if k.lower().startswith("whatsapp:"):
        return k.split(":", 1)[1].strip()
    return k


def normalize_whatsapp_sender(raw: str) -> str:
    """Normalize Twilio/Meta From values for WHATSAPP_USER_MAP lookup."""
    return _normalize_phone_map_key(raw)


@dataclass(frozen=True)
class CapabilitySet:
    enable_whatsapp_channel: bool
    enable_life_assistant: bool
    enable_productivity_agent: bool


def get_capabilities() -> CapabilitySet:
    return CapabilitySet(
        enable_whatsapp_channel=bool(settings.ENABLE_WHATSAPP_CHANNEL),
        enable_life_assistant=bool(settings.ENABLE_LIFE_ASSISTANT),
        enable_productivity_agent=bool(settings.ENABLE_PRODUCTIVITY_AGENT),
    )


def parse_whatsapp_user_map(raw: str) -> Dict[str, str]:
    """
    Supports JSON map or comma-separated pairs:
    - JSON: {"+911234":"employee1@example.com"}
    - CSV: +911234=employee1@example.com,+919999=hr1@example.com
    """
    text = (raw or "").strip()
    if not text:
        return {}
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return {
                    _normalize_phone_map_key(str(k)): str(v).strip().lower()
                    for k, v in data.items()
                    if _normalize_phone_map_key(str(k)) and str(v).strip()
                }
        except Exception:
            return {}
    out: Dict[str, str] = {}
    for pair in text.split(","):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip().lower()
        nk = _normalize_phone_map_key(key)
        if nk and value:
            out[nk] = value
    return out


def reverse_whatsapp_email_to_phone(raw: str) -> Dict[str, str]:
    """Email (lowercase) -> phone key as stored in WHATSAPP_USER_MAP (E.164-style without whatsapp: prefix)."""
    forward = parse_whatsapp_user_map(raw)
    return {email: phone for phone, email in forward.items()}
