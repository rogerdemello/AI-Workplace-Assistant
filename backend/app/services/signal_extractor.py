"""Signal extraction: emotion, topic, and severity from a message."""

from __future__ import annotations

from typing import Dict, Iterable


_EMOTION_TERMS = {
    "frustration": ("frustrated", "frustration", "ignored", "fed up"),
    "stress": ("stressed", "stress", "overwhelmed", "burnout", "exhausted"),
    "anger": ("angry", "furious", "rage", "mad"),
    "confusion": ("confused", "unclear", "don't understand", "not sure"),
    "satisfaction": ("happy", "satisfied", "great", "thanks", "appreciate"),
}

_TOPIC_TERMS = {
    "manager_issue": ("manager", "lead", "supervisor", "boss"),
    "workload": ("workload", "too much work", "deadline", "pressure"),
    "salary": ("salary", "pay", "compensation", "ctc", "increment"),
    "recognition": ("recognition", "credit", "appreciation", "ignored"),
    "culture": ("culture", "team culture", "toxic", "environment"),
    "health": ("sick", "fever", "stress", "burnout", "mental"),
}

_HIGH_SEVERITY_TERMS = (
    "harassment",
    "bully",
    "abuse",
    "threat",
    "discrimination",
    "unsafe",
)


def _match_first(text: str, rules: Dict[str, Iterable[str]], default: str) -> str:
    for label, words in rules.items():
        if any(w in text for w in words):
            return label
    return default


def extract_signals(message_text: str, sentiment_label: str) -> Dict[str, str]:
    text = (message_text or "").lower()
    emotion = _match_first(text, _EMOTION_TERMS, "neutral")
    topic = _match_first(text, _TOPIC_TERMS, "general")

    severity = "low"
    if any(w in text for w in _HIGH_SEVERITY_TERMS):
        severity = "high"
    elif sentiment_label == "negative" and topic in {"manager_issue", "health", "salary"}:
        severity = "high"
    elif sentiment_label == "negative":
        severity = "medium"

    return {
        "emotion": emotion,
        "topic": topic,
        "severity": severity,
    }
