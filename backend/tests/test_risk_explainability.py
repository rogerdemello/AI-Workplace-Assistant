"""A risk score has to be interrogable, not just readable.

HR_METRICS.md tells HR to check which component drives a risk score before
acting on it. Until now nothing exposed that: the four components were computed
and thrown away, leaving a bare number. A score of 46 built entirely from "has
not messaged in two weeks" and one built from repeated distress looked
identical — and only one of them is a person who needs a conversation.
"""

import pytest

from app.services.dashboard_analytics import _explain_risk


def test_no_stored_factors_degrades_quietly():
    for value in (None, {}, {"contributions": None}, "nonsense"):
        out = _explain_risk(value)
        assert out["top_factors"] == []
        assert out["band"] == "low_confidence"
        assert out["factors"] is None


def test_dominant_factor_is_surfaced_first():
    out = _explain_risk(
        {
            "contributions": {
                "negativity": 12.0,
                "inactivity": 20.0,
                "complaints": 0,
                "trend_drop": 4.0,
                "sustained_negative_bump": 0,
            },
            "confidence": {"messages_30d": 30},
        }
    )
    assert out["top_factors"][0].startswith("Inactivity")
    # Zero-weight components are noise on a dashboard.
    assert not any("Complaint" in f for f in out["top_factors"])


def test_silence_and_distress_are_distinguishable():
    """The whole point: two identical scores, two different situations."""
    on_holiday = _explain_risk(
        {
            "contributions": {"negativity": 8.0, "inactivity": 20.0, "complaints": 0, "trend_drop": 0},
            "confidence": {"messages_30d": 2},
        }
    )
    in_trouble = _explain_risk(
        {
            "contributions": {"negativity": 24.0, "inactivity": 0, "complaints": 16.0, "trend_drop": 8.0},
            "confidence": {"messages_30d": 40},
        }
    )
    assert on_holiday["top_factors"][0].startswith("Inactivity")
    assert in_trouble["top_factors"][0].startswith("Negative sentiment")
    # And the thin one is flagged as thin.
    assert on_holiday["band"] == "low_confidence"
    assert in_trouble["band"] == "high_confidence"


@pytest.mark.parametrize(
    "messages,band",
    [(0, "low_confidence"), (4, "low_confidence"), (5, "medium_confidence"), (19, "medium_confidence"), (20, "high_confidence"), (500, "high_confidence")],
)
def test_confidence_band_tracks_sample_size(messages, band):
    out = _explain_risk({"contributions": {"negativity": 10.0}, "confidence": {"messages_30d": messages}})
    assert out["band"] == band
    assert 0.0 <= out["confidence"] <= 1.0


def test_pipeline_persists_the_reasoning(db, test_user):
    """The components must survive the recompute, not just inform it."""
    from app.models.employee_score import EmployeeScore
    from app.services.sentiment_pipeline import SentimentPipelineService

    SentimentPipelineService(db).refresh_employee_aggregate(test_user.id)

    row = db.query(EmployeeScore).filter(EmployeeScore.employee_id == test_user.id).first()
    assert row is not None
    assert isinstance(row.risk_factors, dict), "risk factors were discarded again"
    assert set(row.risk_factors) >= {"contributions", "evidence", "confidence"}
    assert "days_since_last_message" in row.risk_factors["evidence"]
    assert "messages_30d" in row.risk_factors["confidence"]


def test_employee_insights_expose_the_breakdown(db, test_user):
    from app.services.dashboard_analytics import employee_insights_for_hr
    from app.services.sentiment_pipeline import SentimentPipelineService

    SentimentPipelineService(db).refresh_employee_aggregate(test_user.id)
    rows = employee_insights_for_hr(db)

    mine = [r for r in rows if r["id"] == str(test_user.id)]
    assert mine, "employee missing from insights"
    row = mine[0]
    assert row["risk_factors"] is not None
    assert row["risk_calibration_band"] in {
        "low_confidence",
        "medium_confidence",
        "high_confidence",
    }
