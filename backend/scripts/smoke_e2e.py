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
        # HR
        hr_t = _login("hr1@infeedo.ai")
        status, me = _request("GET", "/api/v1/auth/me", headers=_hdr(hr_t))
        assert status == 200 and me.get("email")
        status, users = _request("GET", "/api/v1/users", headers=_hdr(hr_t))
        assert status == 200 and isinstance(users, list) and len(users) >= 2
        status, emps = _request("GET", "/api/v1/analytics/employees", headers=_hdr(hr_t))
        assert status == 200 and isinstance(emps, list)
        status, dash = _request("GET", "/api/v1/analytics/dashboard", headers=_hdr(hr_t))
        assert status == 200 and isinstance(dash, dict)
        print("[ok] HR auth, /users, /analytics/employees, /analytics/dashboard")

        # Employee chat + tickets
        em_t = _login("employee1@infeedo.ai")
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

        # Manager team (optional for DBs where userrole enum lacks manager)
        try:
            mgr_t = _login("manager1@infeedo.ai")
            status, team = _request("GET", "/api/v1/analytics/manager/team", headers=_hdr(mgr_t))
            assert status == 200 and isinstance(team, list)
            print(f"[ok] Manager auth, manager team insights ({len(team)} row(s))")
        except Exception as manager_exc:
            print(f"[warn] Manager path skipped: {manager_exc}")
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
