import pytest

from app.services.sentiment_llm import _parse_llm_sentiment_json
from app.services.sentiment import SentimentService
from app.config import settings


def test_parse_llm_json_plain():
    raw = '{"sentiment":"negative","score":-0.72}'
    out = _parse_llm_sentiment_json(raw)
    assert out == {"sentiment": "negative", "score": -0.72}


def test_parse_llm_json_markdown_fence():
    raw = '```json\n{"sentiment":"neutral","score":0.05}\n```'
    out = _parse_llm_sentiment_json(raw)
    assert out == {"sentiment": "neutral", "score": 0.05}


def test_parse_llm_json_extra_text():
    raw = 'Here you go: {"sentiment":"positive","score":0.88} thanks.'
    out = _parse_llm_sentiment_json(raw)
    assert out == {"sentiment": "positive", "score": 0.88}


def test_parse_llm_json_invalid_returns_none():
    assert _parse_llm_sentiment_json("not json") is None
    assert _parse_llm_sentiment_json('{"sentiment":"maybe","score":0}') is None


def test_analyze_stays_lexicon_when_hybrid_off(monkeypatch):
    monkeypatch.setattr(settings, "USE_ENHANCED_SENTIMENT", False)
    monkeypatch.setattr(settings, "SENTIMENT_HYBRID_ENABLED", False)
    svc = SentimentService()
    r = svc.analyze("This is very helpful and amazing")
    assert r["source"] == "lexicon"
    assert r["sentiment"] == "positive"


def test_analyze_uses_llm_when_enabled_and_mock_returns(monkeypatch):
    monkeypatch.setattr(settings, "USE_ENHANCED_SENTIMENT", False)
    monkeypatch.setattr(settings, "SENTIMENT_HYBRID_ENABLED", True)
    # Avoid hybrid merge path so we assert pure LLM output.
    monkeypatch.setattr(settings, "SENTIMENT_BLEND_SCORE_GAP_THRESHOLD", 99.0)

    def fake_llm(text: str):
        return {"sentiment": "neutral", "score": 0.0, "source": "llm"}

    monkeypatch.setattr(
        "app.services.sentiment.analyze_sentiment_with_llm",
        fake_llm,
    )
    svc = SentimentService()
    r = svc.analyze("whatever the employee said")
    assert r["source"] == "llm"
    assert r["sentiment"] == "neutral"
    assert r["score"] == 0.0


def test_analyze_hybrid_when_llm_and_lexicon_disagree(monkeypatch):
    monkeypatch.setattr(settings, "USE_ENHANCED_SENTIMENT", False)
    monkeypatch.setattr(settings, "SENTIMENT_HYBRID_ENABLED", True)
    monkeypatch.setattr(settings, "SENTIMENT_BLEND_ON_DISAGREEMENT", True)
    monkeypatch.setattr(settings, "SENTIMENT_BLEND_SCORE_GAP_THRESHOLD", 0.15)

    def fake_llm(text: str):
        return {"sentiment": "positive", "score": 0.85, "source": "llm"}

    monkeypatch.setattr(
        "app.services.sentiment.analyze_sentiment_with_llm",
        fake_llm,
    )
    svc = SentimentService()
    r = svc.analyze("I hate this terrible awful worst experience and I'm angry")
    assert r["source"] == "hybrid"
    assert -1.0 <= r["score"] <= 1.0
