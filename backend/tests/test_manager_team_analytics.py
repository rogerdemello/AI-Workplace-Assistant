import uuid
from datetime import timedelta

from app.auth import create_access_token, hash_password
from app.core.time import utcnow_naive
from app.models.sentiment_log import SentimentLog
from app.models.user import User, UserRole, UserStatus


def _auth_headers_for(user_id: uuid.UUID, role: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id), "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_manager_can_view_only_direct_reports(client, db):
    manager = User(
        id=uuid.uuid4(),
        email="mgr-team@example.com",
        name="Mgr Team",
        hashed_password=hash_password("manager123"),
        role=UserRole.manager,
        status=UserStatus.active,
    )
    report = User(
        id=uuid.uuid4(),
        email="report-team@example.com",
        name="Direct Report",
        hashed_password=hash_password("report123"),
        role=UserRole.employee,
        status=UserStatus.active,
        manager_id=manager.id,
    )
    other = User(
        id=uuid.uuid4(),
        email="other-team@example.com",
        name="Other Employee",
        hashed_password=hash_password("other123"),
        role=UserRole.employee,
        status=UserStatus.active,
    )
    db.add_all([manager, report, other])
    db.commit()

    headers = _auth_headers_for(manager.id, "manager")
    response = client.get("/api/v1/analytics/manager/team", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    assert any(row["id"] == str(report.id) for row in rows)
    assert all(row["id"] != str(other.id) for row in rows)


def test_employee_cannot_view_manager_team_analytics(client, auth_headers):
    response = client.get("/api/v1/analytics/manager/team", headers=auth_headers)
    assert response.status_code == 403


def test_hr_can_view_emotion_trends(client, db):
    hr = User(
        id=uuid.uuid4(),
        email="hr-emotions@example.com",
        name="HR Emotions",
        hashed_password=hash_password("hr123"),
        role=UserRole.hr,
        status=UserStatus.active,
    )
    employee = User(
        id=uuid.uuid4(),
        email="emp-emotions@example.com",
        name="Emp Emotions",
        hashed_password=hash_password("emp123"),
        role=UserRole.employee,
        status=UserStatus.active,
    )
    db.add_all([hr, employee])
    db.commit()

    now = utcnow_naive()
    db.add_all(
        [
            SentimentLog(
                employee_id=employee.id,
                message_id=uuid.uuid4(),
                score=30,
                label="negative",
                emotion="stress",
                created_at=now - timedelta(days=1),
            ),
            SentimentLog(
                employee_id=employee.id,
                message_id=uuid.uuid4(),
                score=28,
                label="negative",
                emotion="stress",
                created_at=now - timedelta(days=1),
            ),
            SentimentLog(
                employee_id=employee.id,
                message_id=uuid.uuid4(),
                score=35,
                label="negative",
                emotion="frustration",
                created_at=now - timedelta(days=1),
            ),
        ]
    )
    db.commit()

    headers = _auth_headers_for(hr.id, "hr")
    response = client.get("/api/v1/analytics/emotions?days=3", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    assert len(rows) == 3
    populated = [row for row in rows if row.get("emotions")]
    assert populated
    emotion_mix = populated[-1]["emotions"]
    assert "stress" in emotion_mix
    assert "frustration" in emotion_mix


def test_employee_cannot_view_emotion_trends(client, auth_headers):
    response = client.get("/api/v1/analytics/emotions", headers=auth_headers)
    assert response.status_code == 403


def test_manager_emotion_trend_only_includes_direct_reports(client, db):
    manager = User(
        id=uuid.uuid4(),
        email="mgr-emotion@example.com",
        name="Mgr Emotion",
        hashed_password=hash_password("manager123"),
        role=UserRole.manager,
        status=UserStatus.active,
    )
    report = User(
        id=uuid.uuid4(),
        email="report-emotion@example.com",
        name="Report Emotion",
        hashed_password=hash_password("report123"),
        role=UserRole.employee,
        status=UserStatus.active,
        manager_id=manager.id,
    )
    other = User(
        id=uuid.uuid4(),
        email="other-emotion@example.com",
        name="Other Emotion",
        hashed_password=hash_password("other123"),
        role=UserRole.employee,
        status=UserStatus.active,
    )
    db.add_all([manager, report, other])
    db.commit()

    now = utcnow_naive()
    db.add_all(
        [
            SentimentLog(
                employee_id=report.id,
                message_id=uuid.uuid4(),
                score=30,
                label="negative",
                emotion="stress",
                created_at=now - timedelta(days=1),
            ),
            SentimentLog(
                employee_id=other.id,
                message_id=uuid.uuid4(),
                score=28,
                label="negative",
                emotion="anger",
                created_at=now - timedelta(days=1),
            ),
        ]
    )
    db.commit()

    headers = _auth_headers_for(manager.id, "manager")
    response = client.get("/api/v1/analytics/manager/emotions?days=3", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    populated = [row for row in rows if row.get("emotions")]
    assert populated
    mix = populated[-1]["emotions"]
    assert "stress" in mix
    assert "anger" not in mix


def test_employee_cannot_view_manager_emotion_trends(client, auth_headers):
    response = client.get("/api/v1/analytics/manager/emotions", headers=auth_headers)
    assert response.status_code == 403


def test_manager_classifier_drift_timeseries_only_direct_reports(client, db):
    manager = User(
        id=uuid.uuid4(),
        email="mgr-class@example.com",
        name="Mgr Class",
        hashed_password=hash_password("manager123"),
        role=UserRole.manager,
        status=UserStatus.active,
    )
    report = User(
        id=uuid.uuid4(),
        email="report-class@example.com",
        name="Report Class",
        hashed_password=hash_password("report123"),
        role=UserRole.employee,
        status=UserStatus.active,
        manager_id=manager.id,
    )
    other = User(
        id=uuid.uuid4(),
        email="other-class@example.com",
        name="Other Class",
        hashed_password=hash_password("other123"),
        role=UserRole.employee,
        status=UserStatus.active,
    )
    db.add_all([manager, report, other])
    db.commit()

    now = utcnow_naive()
    db.add_all(
        [
            SentimentLog(
                employee_id=report.id,
                message_id=uuid.uuid4(),
                score=30,
                label="negative",
                emotion="stress",
                analysis_source="lexicon",
                created_at=now - timedelta(days=1),
            ),
            SentimentLog(
                employee_id=other.id,
                message_id=uuid.uuid4(),
                score=28,
                label="negative",
                emotion="anger",
                analysis_source="llm",
                created_at=now - timedelta(days=1),
            ),
        ]
    )
    db.commit()

    headers = _auth_headers_for(manager.id, "manager")
    response = client.get("/api/v1/analytics/manager/sentiment/source-drift/timeseries?days=3", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    populated = [r for r in rows if r.get("sources")]
    assert populated
    last = populated[-1]["sources"]
    assert "lexicon" in last
    assert "llm" not in last


def test_employee_cannot_view_manager_classifier_drift_timeseries(client, auth_headers):
    response = client.get(
        "/api/v1/analytics/manager/sentiment/source-drift/timeseries",
        headers=auth_headers,
    )
    assert response.status_code == 403
