#!/usr/bin/env python3
"""Full CRUD-lifecycle probe — covers by-id GETs and DELETEs the param-less
sweeps skipped. Creates real resources, reads them back by id, updates, and
deletes. Any 5xx (or unexpected non-2xx on a valid step) is flagged.
"""
from __future__ import annotations
import json, os, urllib.request, urllib.error, urllib.parse
from datetime import date, datetime, timedelta

BASE = os.environ.get("SMOKE_API_URL", "http://127.0.0.1:8099").rstrip("/")
results = []


def req(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"} if data else {}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            raw = resp.read().decode(errors="replace")
            return resp.status, (json.loads(raw) if raw and raw.strip().startswith(("{", "[")) else raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, (json.loads(raw) if raw else None)
        except json.JSONDecodeError:
            return e.code, {"detail": raw[:160]}
    except Exception as e:
        return 599, {"detail": repr(e)}


def step(label, method, path, body=None, token=None, ok=(200, 201, 204)):
    st, payload = req(method, path, body, token)
    good = st in ok
    results.append((good, st, label))
    print(f"  [{st}] {'ok ' if good else 'XX '} {label}")
    return st, payload


def login(email, pwd="password123"):
    s, d = req("POST", "/api/v1/auth/login", {"email": email, "password": pwd})
    return d["access_token"] if s == 200 and d else None


def main():
    hr = login("hr1@mark.ai")
    emp = login("emp1@mark.ai")

    # An admin is needed for room CRUD — provision one via invite, then log in.
    st, inv = req("POST", "/api/v1/users",
                  {"name": "Probe Admin", "email": "probe.admin@example.com", "role": "admin"}, hr)
    admin = None
    if st == 201 and isinstance(inv, dict):
        admin = login("probe.admin@example.com", inv["temp_password"])
    elif st == 409:
        admin = None  # already exists from a prior run; skip admin-only steps gracefully
    print(f"admin provisioned: {bool(admin)}")

    print("\n-- Rooms lifecycle --")
    room_id = None
    if admin:
        st, room = step("POST /rooms (admin create)", "POST", "/api/v1/rooms",
                        {"name": "Probe Room", "capacity": 6, "location": "HQ"}, admin)
        room_id = room.get("id") if isinstance(room, dict) else None
    if room_id:
        step("GET /rooms/{id}", "GET", f"/api/v1/rooms/{room_id}", token=emp)
        d = date.today().isoformat()
        step("GET /rooms/{id}/availability", "GET", f"/api/v1/rooms/{room_id}/availability?date={d}", token=emp)
        s = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        e = s + timedelta(hours=1)
        st, bk = step("POST /rooms/book", "POST", "/api/v1/rooms/book",
                      {"room_id": room_id, "title": "Probe sync", "start_time": s.isoformat(), "end_time": e.isoformat()}, emp)
        bid = bk.get("id") if isinstance(bk, dict) else None
        step("GET /rooms/bookings/my", "GET", "/api/v1/rooms/bookings/my", token=emp)
        if bid:
            step("DELETE /rooms/bookings/{id}", "DELETE", f"/api/v1/rooms/bookings/{bid}", token=emp)
        step("DELETE /rooms/{id} (admin)", "DELETE", f"/api/v1/rooms/{room_id}", token=admin)

    print("\n-- Webhooks lifecycle --")
    st, wh = step("POST /webhooks", "POST", "/api/v1/webhooks",
                  {"name": "Probe hook", "url": "https://example.com/hook", "event_type": "ticket_created"}, hr)
    wid = wh.get("id") if isinstance(wh, dict) else None
    if wid:
        step("GET /webhooks/{id}", "GET", f"/api/v1/webhooks/{wid}", token=hr)
        step("GET /webhooks/{id}/deliveries", "GET", f"/api/v1/webhooks/{wid}/deliveries", token=hr)
        step("PATCH /webhooks/{id}", "PATCH", f"/api/v1/webhooks/{wid}", {"name": "Probe hook v2"}, hr)
        step("DELETE /webhooks/{id}", "DELETE", f"/api/v1/webhooks/{wid}", token=hr)

    print("\n-- Surveys lifecycle --")
    st, sv = step("POST /surveys", "POST", "/api/v1/surveys",
                  {"title": "Probe survey", "description": "x",
                   "questions": [{"id": "q1", "type": "rating", "question": "ok?"}], "survey_type": "pulse"}, hr)
    sid = sv.get("id") if isinstance(sv, dict) else None
    if sid:
        step("GET /surveys/{id}", "GET", f"/api/v1/surveys/{sid}", token=emp)
        step("POST /surveys/{id}/respond", "POST", f"/api/v1/surveys/{sid}/respond", {"responses": {"q1": 5}}, emp)
        step("GET /surveys/{id}/responses", "GET", f"/api/v1/surveys/{sid}/responses", token=hr)
        step("DELETE /surveys/{id}", "DELETE", f"/api/v1/surveys/{sid}", token=hr)

    print("\n-- Wellbeing reminders lifecycle --")
    st, rm = step("POST /wellbeing/reminders", "POST", "/api/v1/wellbeing/reminders",
                  {"reminder_type": "custom", "title": "Standup", "message": "Daily standup",
                   "schedule_kind": "one_time", "run_at": "2026-12-01T09:00:00"}, emp)
    rid = rm.get("id") if isinstance(rm, dict) else None
    if rid:
        step("PATCH /wellbeing/reminders/{id}", "PATCH", f"/api/v1/wellbeing/reminders/{rid}", {"title": "Standup v2"}, emp)
        step("DELETE /wellbeing/reminders/{id}", "DELETE", f"/api/v1/wellbeing/reminders/{rid}", token=emp)

    print("\n-- Wellness tips by type --")
    step("GET /wellness/tips/{tip_type}", "GET", "/api/v1/wellness/tips/stretch", token=emp)

    print("\n-- Buddies assignment --")
    st, users = req("GET", "/api/v1/users", token=hr)
    if isinstance(users, list) and len(users) >= 2:
        emp_id = next((u["id"] for u in users if u.get("role") == "employee"), users[0]["id"])
        buddy_id = next((u["id"] for u in users if u["id"] != emp_id), users[-1]["id"])
        step("POST /buddies/assign", "POST", "/api/v1/buddies/assign",
             {"user_id": emp_id, "buddy_id": buddy_id}, hr, ok=(200, 201, 400, 409))

    bad = [r for r in results if not r[0]]
    err5 = [r for r in results if r[1] >= 500]
    print(f"\nLifecycle probe: {sum(1 for r in results if r[0])}/{len(results)} steps ok · {len(err5)} 5xx")
    if bad:
        print("Non-2xx steps:")
        for good, st, label in bad:
            print(f"  [{st}] {label}")
    return 1 if err5 else 0


if __name__ == "__main__":
    raise SystemExit(main())
