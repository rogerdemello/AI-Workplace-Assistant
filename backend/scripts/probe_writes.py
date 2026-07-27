#!/usr/bin/env python3
"""Exercise key write/mutation workflows live. 5xx = BROKEN; 2xx/4xx = alive."""
from __future__ import annotations
import json, os, urllib.request, urllib.error
from datetime import date, timedelta

BASE = os.environ.get("SMOKE_API_URL", "http://127.0.0.1:8099").rstrip("/")


def req(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"} if data else {}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode(errors="replace")
            try:
                return resp.status, (json.loads(raw) if raw else None)
            except json.JSONDecodeError:
                return resp.status, {"_raw": raw[:100]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, (json.loads(raw) if raw else None)
        except json.JSONDecodeError:
            return e.code, {"detail": raw[:200]}
    except Exception as e:
        return 599, {"detail": repr(e)}


def login(email):
    s, d = req("POST", "/api/v1/auth/login", {"email": email, "password": "password123"})
    return d["access_token"] if s == 200 and d else None


def main():
    hr = login("hr1@mark.ai")
    emp = login("emp1@mark.ai")
    s, users = req("GET", "/api/v1/users", token=hr)
    emp_id = next((u["id"] for u in users if u.get("role") == "employee"), users[0]["id"])
    hr_id = next((u["id"] for u in users if u.get("role") == "hr"), users[0]["id"])
    tomorrow = (date.today() + timedelta(days=3)).isoformat()
    dayafter = (date.today() + timedelta(days=4)).isoformat()

    cases = [
        ("POST", "/api/v1/appreciation", {"to_user_id": hr_id, "message": "Thanks for the help!"}, emp),
        ("POST", "/api/v1/mood", {"mood": "good", "score": 7, "note": "probe"}, emp),
        ("POST", "/api/v1/feedback", {"category": "general", "message": "probe feedback"}, emp),
        ("POST", "/api/v1/rag/query", {"query": "What is the leave policy?"}, emp),
        ("POST", "/api/v1/surveys", {"title": "Probe survey", "description": "x",
            "questions": [{"id": "q1", "type": "rating", "question": "ok?"}], "survey_type": "pulse"}, hr),
        ("POST", "/api/v1/automations", {"name": "probe rule", "event_type": "ticket_created",
            "conditions": {}, "actions": {"notify_hr": True}}, hr),
        ("POST", "/api/v1/integrations/hrms/sync", {"provider": "workday_hrms", "dry_run": True}, hr),
        ("POST", "/api/v1/integrations/payroll/sync", {"provider": "adp_payroll", "dry_run": True}, hr),
        ("GET", "/api/v1/billing/subscription", None, hr),
        ("GET", "/api/v1/sso/providers", None, None),
        ("PATCH", f"/api/v1/users/{emp_id}", {"designation": "Senior Team Member"}, hr),
        ("POST", "/api/v1/leave", {"start_date": tomorrow, "end_date": dayafter,
            "leave_type": "paid", "reason": "probe"}, emp),
        ("POST", "/api/v1/chat/message", {"message": "I feel a bit stressed today", "conversation_id": None}, emp),
        ("POST", "/api/v1/wellbeing/check-in", {"mood": "okay", "energy": 5}, emp),
        ("POST", "/api/v1/mood/check-in", {"mood": "okay"}, emp),
        ("POST", "/api/v1/surveys/respond", {}, emp),
    ]

    broken, alive = [], 0
    leave_id = None
    for method, path, body, tok in cases:
        st, payload = req(method, path, body, tok)
        tag = "ok " if st < 400 else ("4xx" if st < 500 else "ERR")
        if st >= 500:
            d = payload.get("detail") if isinstance(payload, dict) else payload
            broken.append((st, method, path, str(d)[:140]))
        else:
            alive += 1
        if path == "/api/v1/leave" and st in (200, 201) and isinstance(payload, dict):
            leave_id = payload.get("id")
        print(f"  [{st}] {tag} {method} {path}")

    # Leave approval flow (HR acts on the employee's request).
    if leave_id:
        for act in ("approve", "reject"):
            st, payload = req("POST", f"/api/v1/leave/{leave_id}/{act}", {"comment": "probe"}, hr)
            print(f"  [{st}] {'ok ' if st<400 else ('4xx' if st<500 else 'ERR')} POST /api/v1/leave/{{id}}/{act}")
            if st >= 500:
                broken.append((st, "POST", f"/api/v1/leave/{{id}}/{act}", str(payload)[:140]))
            else:
                alive += 1

    print(f"\nWrites probe: {alive} alive, {len(broken)} BROKEN(5xx)")
    for st, m, p, d in broken:
        print(f"  [{st}] {m} {p}\n        {d}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
