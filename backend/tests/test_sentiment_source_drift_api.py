import uuid
from datetime import timedelta

from app.auth import create_access_token, hash_password
from app.core.time import utcnow_naive
from app.models.sentiment_log import SentimentLog
from app.models.user import User, UserRole, UserStatus


def _headers(user_id: uuid.UUID, role: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id), "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_hr_can_fetch_sentiment_source_drift(client, db):
    hr = User(
        id=uuid.uuid4(),
        email="hr-drift@example.com",
        name="HR Drift",
        hashed_password=hash_password("hr123"),
        role=UserRole.hr,
        status=UserStatus.active,
    )
    emp = User(
        id=uuid.uuid4(),
        email="emp-drift@example.com",
        name="Emp",
        hashed_password=hash_password("e123"),
        role=UserRole.employee,
        status=UserStatus.active,
    )
    db.add_all([hr, emp])
    db.commit()

    now = utcnow_naive()
    db.add_all(
        [
            SentimentLog(
                employee_id=emp.id,
                message_id=uuid.uuid4(),
                score=40,
                label="negative",
                emotion="stress",
                analysis_source="llm",
                created_at=now - timedelta(days=1),
            ),
            SentimentLog(
                employee_id=emp.id,
                message_id=uuid.uuid4(),
                score=45,
                label="neutral",
                emotion="neutral",
                analysis_source="lexicon",
                created_at=now - timedelta(days=2),
            ),
            SentimentLog(
                employee_id=emp.id,
                message_id=uuid.uuid4(),
                score=42,
                label="negative",
                emotion="frustration",
                analysis_source="hybrid",
                created_at=now - timedelta(days=3),
            ),
            SentimentLog(
                employee_id=emp.id,
                message_id=uuid.uuid4(),
                score=50,
                label="neutral",
                emotion="neutral",
                analysis_source=None,
                created_at=now - timedelta(hours=5),
            ),
        ]
    )
    db.commit()

    res = client.get("/api/v1/analytics/sentiment/source-drift?days=7", headers=_headers(hr.id, "hr"))
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 4
    assert body["window_days"] == 7
    assert body["by_source"]["llm"] == 1
    assert body["by_source"]["lexicon"] == 1
    assert body["by_source"]["hybrid"] == 1
    assert body["by_source"]["unknown"] == 1
    assert abs(sum(body["pct_by_source"].values()) - 100.0) < 0.01


def test_employee_cannot_fetch_sentiment_source_drift(client, auth_headers):
    res = client.get("/api/v1/analytics/sentiment/source-drift", headers=auth_headers)
    assert res.status_code == 403


def test_hr_can_fetch_sentiment_source_drift_timeseries(client, db):
    hr = User(
        id=uuid.uuid4(),
        email="hr-ts@example.com",
        name="HR TS",
        hashed_password=hash_password("hr123"),
        role=UserRole.hr,
        status=UserStatus.active,
    )
    emp = User(
        id=uuid.uuid4(),
        email="emp-ts@example.com",
        name="Emp",
        hashed_password=hash_password("e123"),
        role=UserRole.employee,
        status=UserStatus.active,
    )
    db.add_all([hr, emp])
    db.commit()
    now = utcnow_naive()
    db.add(
        SentimentLog(
            employee_id=emp.id,
            message_id=uuid.uuid4(),
            score=40,
            label="negative",
            emotion="stress",
            analysis_source="lexicon",
            created_at=now - timedelta(days=1),
        )
    )
    db.commit()

    res = client.get("/api/v1/analytics/sentiment/source-drift/timeseries?days=7", headers=_headers(hr.id, "hr"))
    assert res.status_code == 200
    rows = res.json()
    assert isinstance(rows, list)
    assert len(rows) == 7
    assert any(isinstance(r.get("sources"), dict) for r in rows)


def test_hr_dashboard_includes_sentiment_source_drift(client, db):
    hr = User(
        id=uuid.uuid4(),
        email="hr-dash-drift@example.com",
        name="HR Dash",
        hashed_password=hash_password("hr123"),
        role=UserRole.hr,
        status=UserStatus.active,
    )
    emp = User(
        id=uuid.uuid4(),
        email="emp-dash@example.com",
        name="Emp",
        hashed_password=hash_password("e123"),
        role=UserRole.employee,
        status=UserStatus.active,
    )
    db.add_all([hr, emp])
    db.commit()
    now = utcnow_naive()
    db.add(
        SentimentLog(
            employee_id=emp.id,
            message_id=uuid.uuid4(),
            score=40,
            label="negative",
            emotion="stress",
            analysis_source="llm",
            created_at=now - timedelta(days=1),
        )
    )
    db.commit()

    res = client.get("/api/v1/analytics/dashboard", headers=_headers(hr.id, "hr"))
    assert res.status_code == 200
    body = res.json()
    assert "sentiment_source_drift" in body
    assert body["sentiment_source_drift"]["total"] >= 1
    assert body["sentiment_source_drift"]["by_source"].get("llm") == 1
