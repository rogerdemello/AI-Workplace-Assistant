"""Metrics collection and the role-gated /metrics endpoint."""

import pytest
from fastapi import status

from app.core import metrics


@pytest.fixture(autouse=True)
def clean_metrics():
    metrics.reset()
    yield
    metrics.reset()


def test_counters_and_labels():
    metrics.increment("widgets_total")
    metrics.increment("widgets_total")
    metrics.increment("widgets_total", {"kind": "blue"})

    counters = metrics.snapshot()["counters"]
    assert counters["widgets_total"] == 2
    assert counters["widgets_total{kind=blue}"] == 1


def test_latency_summary():
    metrics.observe_latency("job_seconds", 1.0)
    metrics.observe_latency("job_seconds", 3.0)

    entry = metrics.snapshot()["latency"]["job_seconds"]
    assert entry["count"] == 2
    assert entry["avg_seconds"] == 2.0
    assert entry["max_seconds"] == 3.0


def test_series_are_bounded():
    """A label derived from user input must not grow memory without limit."""
    for i in range(metrics._MAX_SERIES + 50):
        metrics.increment("unbounded", {"id": str(i)})
    assert len(metrics.snapshot()["counters"]) <= metrics._MAX_SERIES


def test_collection_never_raises():
    """Metrics must never break the request path, whatever they're handed."""
    metrics.increment("x", {"k": None})  # type: ignore[dict-item]
    metrics.observe_latency("y", "not-a-number")  # type: ignore[arg-type]
    assert isinstance(metrics.snapshot(), dict)


def test_metrics_endpoint_requires_hr(client, auth_headers):
    response = client.get("/metrics", headers=auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_metrics_endpoint_returns_snapshot_for_hr(client, hr_auth_headers):
    metrics.increment("sentiment_pipeline_failures_total", {"error": "OperationalError"})

    response = client.get("/metrics", headers=hr_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert (
        body["counters"]["sentiment_pipeline_failures_total{error=OperationalError}"] == 1
    )


def test_http_errors_are_counted_by_route(client, auth_headers):
    """A 4xx/5xx must show up under its route template, not a raw path."""
    client.get("/api/v1/requests/00000000-0000-0000-0000-000000000000", headers=auth_headers)

    counters = metrics.snapshot()["counters"]
    assert any(
        key.startswith("http_client_errors_total") and "{request_id}" in key
        for key in counters
    ), counters


def test_pipeline_failure_is_counted_on_both_paths(db, test_user, monkeypatch):
    """A failure here means an employee's signal never reaches HR — count it.

    Both the synchronous and the deferred path must report: the deferred one is
    the production default, so instrumenting only the sync path would leave the
    metric that matters permanently at zero.
    """
    import app.api.v1.chat as chat_api

    class Boom:
        def __init__(self, *_a, **_kw):
            pass

        def process_message(self, **_kw):
            raise RuntimeError("pipeline exploded")

    monkeypatch.setattr(chat_api, "SentimentPipelineService", Boom)

    class FakeMessage:
        id = test_user.id

    chat_api._run_sentiment_pipeline_for_user_message(
        db,
        employee_id=test_user.id,
        user_message=FakeMessage(),
        message_text="hi",
        sentiment_label="neutral",
        sentiment_score=0.0,
    )
    chat_api._defer_chat_nonblocking_side_effects(
        employee_id=test_user.id,
        conversation_id=None,
        message_text="hi",
        sentiment_score=0.0,
        intent="general_query",
        sentiment_label="neutral",
        pipeline_message_id=test_user.id,
    )

    counters = metrics.snapshot()["counters"]
    failures = {k: v for k, v in counters.items() if "sentiment_pipeline_failures" in k}
    assert failures, counters
    assert any("path=deferred" in key for key in failures), (
        "deferred pipeline failures are uncounted — that's the production default"
    )
    assert any("path=deferred" not in key for key in failures), (
        "synchronous pipeline failures are uncounted"
    )
    assert "sentiment_pipeline_seconds" in metrics.snapshot()["latency"]
