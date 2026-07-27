#!/usr/bin/env python3
"""Exhaustive read probe: hit every GET endpoint as HR, flag 5xx as broken.

Path params are filled from live IDs gathered at runtime. 2xx/3xx = ok,
4xx = expected (auth/validation/not-found), 5xx = BROKEN.
"""
from __future__ import annotations
import json, os, sys, urllib.request, urllib.error

BASE = os.environ.get("SMOKE_API_URL", "http://127.0.0.1:8099").rstrip("/")
PASS = "password123"


def req(method, path, body=None, token=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {}
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            raw = resp.read().decode(errors="replace")
            try:
                return resp.status, (json.loads(raw) if raw else None)
            except json.JSONDecodeError:
                return resp.status, {"_raw": raw[:120]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = {"detail": raw[:200]}
        return e.code, payload
    except Exception as e:
        return 599, {"detail": f"client error: {e!r}"}


def login(email):
    s, d = req("POST", "/api/v1/auth/login", {"email": email, "password": PASS})
    return d["access_token"] if s == 200 and d else None


def main():
    hr = login("hr1@mark.ai")
    emp = login("emp1@mark.ai")
    if not hr or not emp:
        print("LOGIN FAILED"); return 1

    # Gather live IDs to fill path params.
    ids = {}
    s, users = req("GET", "/api/v1/users", token=hr)
    if isinstance(users, list) and users:
        ids["user_id"] = users[0]["id"]
        for u in users:
            if u.get("role") == "employee":
                ids["user_id"] = u["id"]; ids["employee_id"] = u["id"]; break
    s, tix = req("GET", "/api/v1/tickets", token=hr)
    if isinstance(tix, list) and tix:
        ids["ticket_id"] = tix[0]["id"]
    s, lv = req("GET", "/api/v1/leave", token=emp)
    if isinstance(lv, list) and lv:
        ids["leave_id"] = lv[0]["id"]; ids["request_id"] = lv[0]["id"]
    s, sv = req("GET", "/api/v1/surveys", token=hr)
    if isinstance(sv, list) and sv:
        ids["survey_id"] = sv[0]["id"]
    s, conv = req("GET", "/api/v1/chat/conversations", token=emp)
    if isinstance(conv, list) and conv:
        ids["conversation_id"] = conv[0].get("id")

    with urllib.request.urlopen(f"{BASE}/openapi.json", timeout=10) as r:
        spec = json.load(r)

    import re
    from collections import Counter
    broken, skipped, ok = [], [], 0
    by_code = Counter()
    auth_fail = []  # 401 with HR token = concerning
    for path, ops in sorted(spec["paths"].items()):
        if "get" not in ops:
            continue
        if "stream" in path or "/sse" in path:  # SSE — would block the probe
            skipped.append(path + " (stream)"); continue
        filled = path
        missing = False
        if "{" in path:
            for param in re.findall(r"\{([^}]+)\}", path):
                if param in ids and ids[param]:
                    filled = filled.replace(f"{{{param}}}", str(ids[param]))
                else:
                    missing = True
            if missing:
                skipped.append(path); continue
        # HR first; if blocked by role, retry as employee.
        status, payload = req("GET", filled, token=hr)
        if status in (401, 403):
            status, payload = req("GET", filled, token=emp)
        by_code[status] += 1
        if status >= 500:
            detail = (payload or {}).get("detail") if isinstance(payload, dict) else payload
            broken.append((status, filled, str(detail)[:160]))
        elif status == 401:
            auth_fail.append(filled)
        elif status < 400:
            ok += 1

    print(f"GET probe: {ok} ok · status mix {dict(sorted(by_code.items()))} · {len(skipped)} skipped · {len(broken)} BROKEN(5xx)")
    if broken:
        print("\n=== BROKEN (5xx) ===")
        for st, p, d in broken:
            print(f"  [{st}] {p}\n        {d}")
    if auth_fail:
        print("\n=== 401 even with valid token (concerning) ===")
        for p in auth_fail:
            print(f"  {p}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
