"""Alert thresholds must actually respond to configuration.

These previously read via ``getattr(settings, "SENTIMENT_ALERT_THRESHOLD", 30)``
against names that were never declared on Settings, so the fallback always won
and no deployment could tune them. Pin the wiring, not just the defaults.
"""

import pytest

from app.config import settings
from app.services.sentiment_alerts import (
    DEFAULT_EMOTION_ALERTS,
    SentimentAlertService,
    _parse_emotion_triggers,
)


def test_thresholds_are_declared_on_settings():
    for name in (
        "SENTIMENT_ALERT_THRESHOLD",
        "RISK_ALERT_THRESHOLD",
        "ALERT_COOLDOWN_MINUTES",
        "EMOTION_ALERT_TRIGGERS",
    ):
        assert hasattr(settings, name), f"{name} is not configurable"


def test_service_picks_up_configured_thresholds(db, monkeypatch):
    monkeypatch.setattr(settings, "SENTIMENT_ALERT_THRESHOLD", 12)
    monkeypatch.setattr(settings, "RISK_ALERT_THRESHOLD", 88)
    monkeypatch.setattr(settings, "ALERT_COOLDOWN_MINUTES", 5)

    service = SentimentAlertService(db)
    assert service.sentiment_threshold == 12
    assert service.risk_threshold == 88
    assert service.cooldown_minutes == 5


def test_emotion_triggers_parse_from_csv(db, monkeypatch):
    monkeypatch.setattr(settings, "EMOTION_ALERT_TRIGGERS", "burnout, Panic ,despair")

    service = SentimentAlertService(db)
    assert service.emotion_alerts == {"burnout", "panic", "despair"}


@pytest.mark.parametrize("bad", ["", "   ", ",,,", None, 42])
def test_unparseable_triggers_fall_back_rather_than_disabling_alerts(bad):
    """A config typo must not silently switch emotion alerting off."""
    assert _parse_emotion_triggers(bad) == set(DEFAULT_EMOTION_ALERTS)


def test_defaults_still_apply_out_of_the_box(db):
    service = SentimentAlertService(db)
    assert service.sentiment_threshold == 30
    assert service.risk_threshold == 70
    assert "burnout" in service.emotion_alerts
