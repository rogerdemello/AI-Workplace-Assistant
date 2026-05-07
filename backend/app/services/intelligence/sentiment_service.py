"""
MARK intelligence — LLM sentiment for production dashboards (user messages only).

Runs early in the chat orchestrator; persistence happens after the user message is saved
(via SentimentPipelineService + optional conversation_id on sentiment_logs).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from ...ai_client import get_ai_client
from ...config import settings
from ..sentiment import SentimentService
from ..sentiment_llm import azure_credentials_usable

logger = logging.getLogger(__name__)

_INTELLIGENCE_SKIP = frozenset(
    {
        "ok",
        "okay",
        "yes",
        "yeah",
        "yep",
        "no",
        "nope",
        "k",
        "kk",
        "hi",
        "hey",
        "thanks",
        "thank you",
        "sure",
        "fine",
    }
)


class IntelligenceSentimentSnapshot(BaseModel):
    """Normalized output aligned with HR dashboards (0 = very negative, 100 = very positive)."""

    score_0_100: int = Field(ge=0, le=100)
    label: str  # positive | neutral | negative
    emotion: str = Field(max_length=80)
    topic: Optional[str] = Field(default=None, max_length=80)
    analysis_source: str = "llm_intelligence"


def _should_skip_message(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 3:
        return True
    low = t.lower().strip("!.,")
    if low in _INTELLIGENCE_SKIP:
        return True
    return False


def _extract_json_object(raw: str) -> Optional[Dict[str, Any]]:
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _snapshot_from_llm_dict(obj: Dict[str, Any]) -> Optional[IntelligenceSentimentSnapshot]:
    try:
        score = int(round(float(obj.get("score", 50))))
    except (TypeError, ValueError):
        score = 50
    score = max(0, min(100, score))
    label = str(obj.get("label", obj.get("sentiment", "neutral"))).lower().strip()
    if label not in ("positive", "neutral", "negative"):
        # Allow legacy "sentiment" key from older prompts
        alt = str(obj.get("sentiment", "")).lower().strip()
        if alt in ("positive", "neutral", "negative"):
            label = alt
        else:
            label = "neutral"
    emotion = str(obj.get("emotion", "neutral")).strip() or "neutral"
    topic = obj.get("topic")
    topic_s = str(topic).strip()[:80] if topic is not None else None
    return IntelligenceSentimentSnapshot(
        score_0_100=score,
        label=label,
        emotion=emotion[:80],
        topic=topic_s or None,
        analysis_source="llm_intelligence",
    )


def _lexicon_fallback(text: str) -> IntelligenceSentimentSnapshot:
    svc = SentimentService(db=None)
    lex = svc.analyze_lexicon_only(text)
    raw = float(lex.get("score", 0.0))
    score = int(max(0, min(100, round((raw + 1.0) * 50.0))))
    label = str(lex.get("sentiment", "neutral"))
    if label not in ("positive", "neutral", "negative"):
        label = "neutral"
    return IntelligenceSentimentSnapshot(
        score_0_100=score,
        label=label,
        emotion="neutral",
        topic=None,
        analysis_source="lexicon_fallback",
    )


def analyze_user_message_intelligence(text: str) -> Optional[Dict[str, Any]]:
    """
    User-authored chat text only (caller must not pass assistant replies).

    Returns a dict suitable for flow_context / SentimentPipelineService, or None if skipped.
    """
    if not settings.ENABLE_MARK_INTELLIGENCE_PIPELINE:
        return None
    if _should_skip_message(text):
        return None

    if settings.INTELLIGENCE_USE_LLM and azure_credentials_usable():
        prompt = f"""Analyze sentiment of the employee message for HR intelligence.

Return ONLY valid JSON (no markdown) with this shape:
{{
  "score": <integer 0-100, 0=very negative, 50=neutral, 100=very positive>,
  "label": "positive" | "neutral" | "negative",
  "emotion": "<single lowercase word or short phrase, e.g. frustration, gratitude>",
  "topic": "<short topic slug or null, e.g. manager_issue, workload, payroll, general>"
}}

Message: {text[: settings.SENTIMENT_LLM_MAX_CHARS]}"""

        try:
            client = get_ai_client(use_mock=False)
            resp = client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You output compact JSON only. No prose.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=120,
            )
            raw_content = resp["choices"][0]["message"]["content"]
            obj = _extract_json_object(raw_content)
            if obj:
                snap = _snapshot_from_llm_dict(obj)
                if snap:
                    return snap.model_dump()
        except Exception:
            logger.warning("Intelligence LLM sentiment failed; using lexicon fallback", exc_info=True)

    fb = _lexicon_fallback(text)
    return fb.model_dump()


def enqueue_intelligence_follow_up(_text: str, _employee_id: str) -> None:
    """Reserved for async workers (Redis/Celery). No-op in MVP sync pipeline."""
    if settings.INTELLIGENCE_ASYNC_QUEUE_ENABLED:
        logger.debug("INTELLIGENCE_ASYNC_QUEUE_ENABLED is set but no worker is wired yet.")
