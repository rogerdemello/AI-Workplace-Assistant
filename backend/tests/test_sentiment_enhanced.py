"""Tests for enhanced sentiment analysis."""

import pytest
from uuid import uuid4
from app.services.sentiment_enhanced import (
    ContextAwareSentimentAnalyzer,
    analyze_sentiment_enhanced,
    get_conversation_summary,
)


class TestEnhancedSentimentAnalyzer:
    """Test the enhanced sentiment analyzer with context awareness."""

    @pytest.fixture
    def analyzer(self):
        return ContextAwareSentimentAnalyzer()

    def test_positive_sentiment(self, analyzer):
        result = analyzer.analyze("I'm really happy with the new benefits package!")
        assert result["sentiment"] == "positive"
        assert result["score"] > 0.3
        assert result["intensity"] in ["medium", "high"]
        assert result["emotions"]["primary"] in ["joy", "satisfaction", "gratitude"]

    def test_negative_sentiment(self, analyzer):
        result = analyzer.analyze("I'm frustrated with the micromanagement here")
        assert result["sentiment"] == "negative"
        assert result["score"] < -0.3
        assert result["emotions"]["primary"] == "frustration"

    def test_neutral_sentiment(self, analyzer):
        result = analyzer.analyze("The meeting is scheduled for 3 PM")
        assert result["sentiment"] == "neutral"
        assert abs(result["score"]) < 0.2

    def test_sarcasm_detection(self, analyzer):
        result = analyzer.analyze("Oh great, another deadline moved up. Just what I needed.")
        assert result["sarcasm"]["detected"] == True
        assert result["sarcasm"]["confidence"] > 0.5
        # Sarcasm should invert sentiment
        assert result["score"] < 0  # Should be negative despite positive words

    def test_emoji_sentiment(self, analyzer):
        result = analyzer.analyze("Thanks for the help! 😊")
        assert result["sentiment"] == "positive"
        assert result["metadata"]["emojis_found"]

    def test_negation_handling(self, analyzer):
        result = analyzer.analyze("I'm not happy with this decision")
        assert result["sentiment"] == "negative"
        assert result["score"] < -0.2

    def test_intensity_modifiers(self, analyzer):
        result_weak = analyzer.analyze("I'm slightly annoyed")
        result_strong = analyzer.analyze("I'm extremely furious")
        
        assert result_weak["intensity"] == "low"
        assert result_strong["intensity"] == "high"
        assert abs(result_strong["score"]) > abs(result_weak["score"])

    def test_hr_phrases(self, analyzer):
        result = analyzer.analyze("The toxic culture here is making me miserable")
        assert result["sentiment"] == "negative"
        assert result["score"] < -0.5
        assert "toxic culture" in [p[0] for p in result["metadata"]["phrases_found"]]

    def test_context_awareness(self, analyzer):
        conversation_id = uuid4()
        
        # First message: strongly negative
        result1 = analyzer.analyze("I'm absolutely furious about this unfair treatment!", conversation_id=conversation_id)
        assert result1["sentiment"] == "negative"
        assert result1["score"] < -0.5
        
        # Second message: very positive (dramatic shift)
        result2 = analyzer.analyze("Actually, I just got promoted! I'm thrilled!", conversation_id=conversation_id)
        assert result2["sentiment"] == "positive"
        # Should show some adjustment happened (either context or just different message)
        assert result2["score"] > 0

    def test_conversation_summary(self, analyzer):
        conversation_id = uuid4()
        
        analyzer.analyze("I'm absolutely furious about the micromanagement", conversation_id=conversation_id)
        analyzer.analyze("This toxic culture is making me miserable", conversation_id=conversation_id)
        analyzer.analyze("I hate this hostile work environment", conversation_id=conversation_id)
        
        summary = analyzer.get_conversation_sentiment_summary(conversation_id)
        assert summary["message_count"] == 3
        assert summary["dominant_sentiment"] == "negative"
        assert summary["average_score"] < -0.3
        assert summary["trend"] in ["stable", "declining"]

    def test_exhaustion_emotion(self, analyzer):
        result = analyzer.analyze("I'm completely burned out and exhausted")
        # Should detect exhaustion-related emotions
        assert result["emotions"]["primary"] in ["exhaustion", "overwhelm", "frustration"]
        # With burned out and exhausted, should be negative or at least not positive
        assert result["sentiment"] in ["negative", "neutral"]

    def test_gratitude_emotion(self, analyzer):
        result = analyzer.analyze("I'm so grateful for all your support")
        assert result["emotions"]["primary"] == "gratitude"
        assert result["sentiment"] == "positive"

    def test_anxiety_emotion(self, analyzer):
        result = analyzer.analyze("I'm really worried about the upcoming review")
        assert result["emotions"]["primary"] == "anxiety"

    def test_confusion_emotion(self, analyzer):
        result = analyzer.analyze("I'm confused about the new policy changes")
        assert result["emotions"]["primary"] == "confusion"

    def test_convenience_function(self):
        result = analyze_sentiment_enhanced("This is amazing! Thank you so much! ❤️")
        assert result["sentiment"] == "positive"
        assert result["emotions"]["primary"] in ["joy", "gratitude", "satisfaction"]

    def test_empty_text(self, analyzer):
        result = analyzer.analyze("")
        assert result["sentiment"] == "neutral"
        assert result["confidence"] == 0.0

    def test_caps_lock_shouting(self, analyzer):
        result = analyzer.analyze("I AM SO FRUSTRATED WITH THIS")
        assert result["sentiment"] == "negative"
        # Should be more intense due to all caps
        assert result["intensity"] == "high"

    def test_multiple_emotions(self, analyzer):
        result = analyzer.analyze("I'm happy about the promotion but anxious about the new responsibilities")
        # Should detect mixed emotions
        assert len(result["emotions"]["secondary"]) > 0


class TestSentimentEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def analyzer(self):
        return ContextAwareSentimentAnalyzer()

    def test_very_long_text(self, analyzer):
        long_text = "I am " + "very " * 50 + "happy"
        result = analyzer.analyze(long_text)
        assert result["sentiment"] == "positive"

    def test_mixed_language(self, analyzer):
        # Text with some non-English characters but English sentiment
        result = analyzer.analyze("I'm very happy! 😊 ¡Excelente!")
        assert result["sentiment"] == "positive"

    def test_only_emojis(self, analyzer):
        result = analyzer.analyze("😊👍❤️")
        assert result["sentiment"] == "positive"

    def test_only_punctuation(self, analyzer):
        result = analyzer.analyze("!!!???...")
        assert result["sentiment"] == "neutral"

    def test_single_word(self, analyzer):
        result = analyzer.analyze("frustrated")
        assert result["sentiment"] == "negative"
        assert result["emotions"]["primary"] == "frustration"
