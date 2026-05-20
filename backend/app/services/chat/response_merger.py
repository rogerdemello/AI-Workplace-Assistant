"""Compose one human-facing reply from the primary orchestrator plus specialist overlays."""

from __future__ import annotations

from typing import Iterable, List

from ...middleware.security import mask_pii
from ..agents.base import AgentResult


# Overlays below this confidence are dropped so weakly-triggered specialists
# don't pile noise onto the HR voice. Tunable per deployment by editing here.
MIN_OVERLAY_CONFIDENCE = 0.4
# A single overlay should not dominate the reply — clamp prefix/suffix length
# so a misbehaving agent can't spam the user.
MAX_OVERLAY_CHARS = 280


def merge_supplementary(base_reply: str, results: Iterable[AgentResult], *, original_message: str = "") -> str:
    _ = original_message  # reserved for overlap / dedupe heuristics
    prefixes: List[str] = []
    suffixes: List[str] = []
    for r in results:
        if not r.handled:
            continue
        if r.confidence < MIN_OVERLAY_CONFIDENCE:
            continue
        # Mask PII inside overlay text only — the base HR reply legitimately
        # references the user's own email / phone in some flows and shouldn't
        # be redacted. Overlays are specialist-generated and not trusted to
        # know what's safe to surface.
        if r.reply_prefix:
            prefixes.append(mask_pii(r.reply_prefix.strip())[:MAX_OVERLAY_CHARS])
        if r.reply_suffix:
            suffixes.append(mask_pii(r.reply_suffix.strip())[:MAX_OVERLAY_CHARS])

    core = (base_reply or "").strip()
    pre = " ".join(prefixes).strip()
    suf = " ".join(suffixes).strip()

    parts = [p for p in [pre, core, suf] if p]
    if not parts:
        return ""
    merged = " ".join(parts)

    # Light dedupe if prefix repeats the start of core
    if pre and core.lower().startswith(pre.lower()[: min(20, len(pre))]):
        merged = " ".join([core, suf]).strip() if suf else core

    return _normalize_human_response(merged.strip())


def _normalize_human_response(text: str) -> str:
    """Keep final response concise, natural, and non-repetitive."""
    if not text:
        return ""

    # Dedupe repeated sentences while preserving order.
    seen: set[str] = set()
    sentences: List[str] = []
    for raw in text.replace("\n", " ").split("."):
        s = raw.strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        sentences.append(s + ".")

    if not sentences:
        return ""

    # 1-3 short lines max, as a single-assistant voice.
    lines = sentences[:3]
    return "\n".join(lines).strip()
