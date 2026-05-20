#!/usr/bin/env python3
"""
Quick end-to-end probe against a running API (default http://127.0.0.1:8000).

Usage (from repo root or backend/):
  python -m scripts.smoke_e2e
  set SMOKE_API_URL=http://localhost:8000 && python -m scripts.smoke_e2e

Expects seeded users (python -m scripts.seed_dummy_users).
"""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

BASE = os.environ.get("SMOKE_API_URL", "http://127.0.0.1:8000").rstrip("/")
PASS = os.environ.get("SMOKE_PASSWORD", "password123")
# Short default so a dead server fails in seconds, not ~45s+ per call.
_REQUEST_TIMEOUT = max(3, min(120, int(os.environ.get("SMOKE_HTTP_TIMEOUT_SEC", "12"))))


def _request(method: str, path: str, body: dict | None = None, headers: dict | None = None):
    url = f"{BASE}{path}"
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return resp.status, None
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = {"detail": raw}
        raise RuntimeError(f"HTTP {e.code} {path}: {payload}") from e
    except (TimeoutError, socket.timeout, urllib.error.URLError) as e:
        hint = (
            f"cannot reach API at {BASE} (timed out or connection refused). "
            "Start the backend first, e.g. `uvicorn app.main:app --reload` from backend/."
        )
        raise RuntimeError(f"{path}: {hint} Original error: {e!r}") from e


def _login(email: str) -> str:
    status, data = _request("POST", "/api/v1/auth/login", {"email": email, "password": PASS})
    assert status == 200 and data
    token = data.get("access_token")
    if not token:
        raise RuntimeError("No access_token")
    return token


def _hdr(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    failures: list[str] = []
    try:
        # Health probes — these must not require auth.
        status, hz = _request("GET", "/healthz")
        assert status == 200 and hz and hz.get("status") == "ok"
        status, rz = _request("GET", "/readyz")
        # /readyz returns 503 with components when DB is unreachable; smoke
        # assumes the API is healthy, so demand 200.
        assert status == 200 and rz and rz.get("components", {}).get("database", {}).get("status") == "ok"
        print("[ok] /healthz, /readyz")

        # HR
        hr_t = _login("hr1@mark.ai")
        status, me = _request("GET", "/api/v1/auth/me", headers=_hdr(hr_t))
        assert status == 200 and me.get("email")
        status, users = _request("GET", "/api/v1/users", headers=_hdr(hr_t))
        assert status == 200 and isinstance(users, list) and len(users) >= 1
        status, emps = _request("GET", "/api/v1/analytics/employees", headers=_hdr(hr_t))
        assert status == 200 and isinstance(emps, list)
        status, dash = _request("GET", "/api/v1/analytics/dashboard", headers=_hdr(hr_t))
        assert status == 200 and isinstance(dash, dict)
        print("[ok] HR auth, /users, /analytics/employees, /analytics/dashboard")

        # Employee chat + tickets
        em_t = _login("emp1@mark.ai")
        status, _ = _request("GET", "/api/v1/auth/me", headers=_hdr(em_t))
        assert status == 200
        status, tix = _request("GET", "/api/v1/tickets", headers=_hdr(em_t))
        assert status == 200 and isinstance(tix, list)
        status, reply = _request(
            "POST",
            "/api/v1/chat/message",
            {"message": "Hello — quick smoke test.", "conversation_id": None},
            headers=_hdr(em_t),
        )
        assert status == 200 and reply.get("response")
        print("[ok] Employee auth, tickets list, unified chat/message")

        # Ticket creation (employee POSTs a low-noise smoke ticket).
        status, new_ticket = _request(
            "POST",
            "/api/v1/tickets",
            {
                "query": "Smoke test ticket — please ignore.",
                "category": "general",
                "priority": "low",
            },
            headers=_hdr(em_t),
        )
        assert status in (200, 201) and new_ticket and new_ticket.get("id")
        print(f"[ok] Ticket creation (id={new_ticket.get('id')})")

        # Leave request (start_date is tomorrow to satisfy the past-date validator).
        tomorrow = date.today() + timedelta(days=1)
        day_after = date.today() + timedelta(days=2)
        status, new_leave = _request(
            "POST",
            "/api/v1/leave",
            {
                "start_date": tomorrow.isoformat(),
                "end_date": day_after.isoformat(),
                "leave_type": "paid",
                "reason": "Smoke test leave — please ignore.",
            },
            headers=_hdr(em_t),
        )
        assert status in (200, 201) and new_leave and new_leave.get("id")
        print(f"[ok] Leave request (id={new_leave.get('id')})")

        # Sentiment trend should reflect the chat message above (best-effort —
        # the pipeline may be deferred so we only assert the endpoint works).
        status, trend = _request("GET", "/api/v1/sentiment/trend", headers=_hdr(em_t))
        assert status == 200 and isinstance(trend, dict)
        print("[ok] /sentiment/trend reachable")
    except Exception as exc:
        failures.append(str(exc))
        print(f"[fail] {exc}", file=sys.stderr)

    if failures:
        print("\nSmoke failed. Tips:", file=sys.stderr)
        print("  - Backend running?  uvicorn app.main:app --reload", file=sys.stderr)
        print("  - Seed DB:          python -m scripts.seed_dummy_users", file=sys.stderr)
        print(f"  - BASE URL:         {BASE}", file=sys.stderr)
        return 1
    print("\nSmoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
