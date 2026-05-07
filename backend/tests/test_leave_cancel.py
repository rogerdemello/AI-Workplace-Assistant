from datetime import date, timedelta

from fastapi import status


def test_employee_can_cancel_pending_leave(client, auth_headers):
    create_response = client.post(
        "/api/v1/leave",
        headers=auth_headers,
        json={
            "start_date": (date.today() + timedelta(days=3)).isoformat(),
            "end_date": (date.today() + timedelta(days=4)).isoformat(),
            "leave_type": "paid",
            "reason": "Personal errand",
        },
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    leave_id = create_response.json()["id"]

    cancel_response = client.patch(f"/api/v1/leave/{leave_id}/cancel", headers=auth_headers)
    assert cancel_response.status_code == status.HTTP_200_OK
    payload = cancel_response.json()
    assert payload["status"] == "rejected"
    assert payload["review_comment"] == "Cancelled by employee"


def test_employee_cannot_cancel_non_pending_leave(client, auth_headers, hr_auth_headers):
    create_response = client.post(
        "/api/v1/leave",
        headers=auth_headers,
        json={
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "end_date": (date.today() + timedelta(days=8)).isoformat(),
            "leave_type": "paid",
            "reason": "Planned leave",
        },
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    leave_id = create_response.json()["id"]

    approve_response = client.patch(f"/api/v1/leave/{leave_id}/approve", headers=hr_auth_headers)
    assert approve_response.status_code == status.HTTP_200_OK

    cancel_response = client.patch(f"/api/v1/leave/{leave_id}/cancel", headers=auth_headers)
    assert cancel_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "only pending leave requests can be cancelled" in cancel_response.json()["detail"].lower()


def test_overlapping_leave_returns_warning(client, auth_headers):
    base = date.today() + timedelta(days=14)
    response_a = client.post(
        "/api/v1/leave",
        headers=auth_headers,
        json={
            "start_date": base.isoformat(),
            "end_date": (base + timedelta(days=2)).isoformat(),
            "leave_type": "paid",
            "reason": "Vacation",
        },
    )
    assert response_a.status_code == status.HTTP_201_CREATED

    response_b = client.post(
        "/api/v1/leave",
        headers=auth_headers,
        json={
            "start_date": (base + timedelta(days=1)).isoformat(),
            "end_date": (base + timedelta(days=3)).isoformat(),
            "leave_type": "paid",
            "reason": "Vacation part 2",
        },
    )
    assert response_b.status_code == status.HTTP_201_CREATED
    assert "X-Leave-Overlap-Warning" in response_b.headers
    assert "already have leave" in response_b.headers["X-Leave-Overlap-Warning"]
