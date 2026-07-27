"""Tests for fast-path intent classification."""

import pytest
from app.services.intent_classifier import INTENT_LIST, IntentClassifier, _FAST_ROUTES


@pytest.fixture
def classifier():
    return IntentClassifier(ai_client=None, confidence_threshold=0.7)


class TestFastClassify:
    """Validate heuristic fast routes without calling LLM."""

    @pytest.mark.parametrize(
        "message,expected_intent",
        [
            ("I need 3 days off next week", "leave_request"),
            ("Can I apply for leave?", "leave_request"),
            ("I want to book leave", "leave_request"),
            ("Take a day off tomorrow", "leave_request"),
            ("Going on vacation next month", "leave_request"),
            ("How many leaves do I have left?", "policy_query"),
            ("What is my leave balance?", "policy_query"),
            ("How much leave remaining?", "policy_query"),
            ("I have a complaint about my manager", "ticket_create"),
            ("Report an issue with laptop", "ticket_create"),
            ("Something is broken in the office", "ticket_create"),
            ("What is the remote work policy?", "policy_query"),
            ("Tell me about health insurance", "benefits_question"),
            ("Draft an email to my manager", "email_draft"),
            ("I feel stressed and anxious", "emotional"),
            ("I can't cope with the workload", "emotional"),
            ("Hi there!", "general_query"),
            ("Hello, good morning", "general_query"),
            ("Thanks for your help", "general_query"),
            # "help me with X" is the topical-help route (ordered before generic help)
            ("Help me with something", "help_request"),
            # bare "I need help" is generic → general_query
            ("I need help", "general_query"),
        ],
    )
    def test_fast_route_hits(self, classifier, message, expected_intent):
        result = classifier._fast_classify(message)
        assert result is not None, f"Expected fast match for: {message}"
        assert result["intent"] == expected_intent
        assert result["confidence"] >= 0.85

    def test_fast_route_misses_ambiguous(self, classifier):
        # Ambiguous messages should NOT match fast routes
        ambiguous = [
            "Can you tell me something?",
            "What's up?",
            "I have a question",
            "Interesting",
        ]
        for msg in ambiguous:
            result = classifier._fast_classify(msg)
            assert result is None, f"Expected no fast match for: {msg}"

    def test_fast_routes_compiled(self):
        assert len(_FAST_ROUTES) > 0
        for regex, intent, conf, reason in _FAST_ROUTES:
            assert regex.pattern
            # Every fast route must resolve to a declared intent, otherwise the
            # orchestrator has no flow or handler to dispatch it to.
            assert intent in INTENT_LIST
            assert 0.8 <= conf <= 1.0
            assert reason.startswith("Fast-path:")

    def test_cache_key_stable(self, classifier):
        k1 = classifier._cache_key("Hello World")
        k2 = classifier._cache_key("hello world ")
        k3 = classifier._cache_key("HELLO WORLD")
        assert k1 == k2 == k3
        assert k1.startswith("intent_classify:")

    def test_classify_returns_dict(self, classifier, monkeypatch):
        # Mock LLM so we don't hit Azure
        monkeypatch.setattr(
            classifier,
            "_llm_classify",
            lambda msg: {"intent": "general_query", "confidence": 0.5, "reasoning": "mock"},
        )
        result = classifier.classify("Hello")
        assert "intent" in result
        assert "confidence" in result
        assert "reasoning" in result
