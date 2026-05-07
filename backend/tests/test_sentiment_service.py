from app.services.sentiment import SentimentService


def test_sentiment_service_positive_with_amplifier():
    svc = SentimentService()
    result = svc.analyze("This is very helpful and amazing")
    assert result["sentiment"] == "positive"
    assert result["score"] > 0.3


def test_sentiment_service_negative_with_neg_phrase():
    svc = SentimentService()
    result = svc.analyze("My manager ignores me and I am not happy")
    assert result["sentiment"] == "negative"
    assert result["score"] < -0.3


def test_sentiment_service_negation_flips_positive_word():
    svc = SentimentService()
    result = svc.analyze("This is not good")
    assert result["sentiment"] == "negative"


def test_sentiment_service_neutral_for_empty_text():
    svc = SentimentService()
    result = svc.analyze("   ")
    assert result["sentiment"] == "neutral"
    assert result["score"] == 0.0
