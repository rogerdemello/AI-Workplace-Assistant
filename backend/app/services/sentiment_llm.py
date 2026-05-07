"""LLM-based sentiment classification with strict JSON output; used when hybrid mode is enabled."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from ..config import settings

logger = logging.getLogger(__name__)

def _balanced_json_fragment(text: str) -> Optional[str]:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def azure_credentials_usable() -> bool:
    key = (settings.AZURE_OPENAI_API_KEY or "").strip()
    ep = (settings.AZURE_OPENAI_ENDPOINT or "").strip()
    if not key or not ep:
        return False
    if key.lower() in ("mock-key", "your-azure-openai-api-key"):
        return False
    if "mock.openai.azure.com" in ep.lower():
        return False
    return True


def _parse_llm_sentiment_json(raw: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON object with sentiment + score from model output (plain JSON or fenced).
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    # Strip common markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)

    candidates = [text]
    frag = _balanced_json_fragment(text)
    if frag and frag != text:
        candidates.append(frag)

    for candidate in candidates:
        if not candidate:
            continue
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        label = str(obj.get("sentiment", "")).lower().strip()
        if label not in ("positive", "neutral", "negative"):
            continue
        try:
            score = float(obj.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        score = max(-1.0, min(1.0, score))
        return {"sentiment": label, "score": round(score, 3)}
    return None


def analyze_sentiment_with_llm(text: str) -> Optional[Dict[str, Any]]:
    """
    Call Azure chat completion for sentiment. Returns dict with sentiment, score, source='llm'
    or None on any failure (caller falls back to lexicon).
    """
    if not settings.SENTIMENT_HYBRID_ENABLED or not azure_credentials_usable():
        return None

    trimmed = (text or "").strip()
    if not trimmed:
        return None

    max_chars = max(200, int(settings.SENTIMENT_LLM_MAX_CHARS))
    if len(trimmed) > max_chars:
        trimmed = trimmed[:max_chars]

    try:
        from ..ai_client.client import AzureOpenAIClient
    except ImportError:
        return None

    try:
        client = AzureOpenAIClient(
            api_key=settings.AZURE_OPENAI_API_KEY,
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
            deployment=settings.AZURE_OPENAI_DEPLOYMENT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
    except ValueError:
        return None

    system = (
        "You classify short workplace/HR chat messages for wellbeing tone. "
        "Reply with ONLY a JSON object, no markdown, no explanation: "
        '{"sentiment":"positive"|"neutral"|"negative","score":<number>}. '
        "score must be between -1 (very negative affect) and 1 (very positive). "
        "Use neutral when unclear or purely factual. Detect sarcasm or mixed feelings when obvious."
    )
    user = f"Message:\n{trimmed}"

    timeout = max(1.0, float(settings.SENTIMENT_LLM_TIMEOUT_SECONDS))
    try:
        resp = client.chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            max_tokens=120,
            timeout=timeout,
        )
    except Exception as exc:
        logger.warning("LLM sentiment call failed, will use lexicon: %s", exc)
        return None

    try:
        content = resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None

    parsed = _parse_llm_sentiment_json(str(content))
    if not parsed:
        logger.warning("LLM sentiment parse failed, falling back to lexicon")
        return None

    parsed["source"] = "llm"
    return parsed


__all__ = ["analyze_sentiment_with_llm", "azure_credentials_usable", "_parse_llm_sentiment_json"]
