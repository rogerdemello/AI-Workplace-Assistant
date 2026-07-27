#!/usr/bin/env python3
"""Functional per-workflow probe.

Drives every POST/PATCH/PUT endpoint with a VALID payload synthesized from its
OpenAPI requestBody schema (required fields, enums, examples), filling path
params from live IDs. A 4xx/5xx on a schema-valid call is flagged for review —
unlike the earlier guess-based probe, validation failures here mean a real
mismatch, not a bad guess.
"""
from __future__ import annotations
import json, os, re, urllib.request, urllib.error
from datetime import date, timedelta

BASE = os.environ.get("SMOKE_API_URL", "http://127.0.0.1:8099").rstrip("/")
# Endpoints with side effects we don't want to fire, or that need real external
# services / OAuth — skipped with a reason.
SKIP = {
    "/api/v1/auth/login": "tested separately",
    "/api/v1/auth/register": "creates noise users",
    "/api/v1/sso/{provider}/callback": "needs live IdP",
    "/api/v1/sso/{provider}/login": "redirect to IdP",
    "/api/v1/integrations/calendar/{provider}/callback": "needs OAuth code",
}


def req(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"} if data else {}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            raw = resp.read().decode(errors="replace")
            try:
                return resp.status, (json.loads(raw) if raw else None)
            except json.JSONDecodeError:
                return resp.status, {"_raw": raw[:80]}
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


def resolve_schema(spec, node):
    """Resolve a $ref one level (OpenAPI components)."""
    if "$ref" in node:
        name = node["$ref"].split("/")[-1]
        return spec["components"]["schemas"].get(name, {})
    return node


def sample(spec, schema, ids, depth=0):
    """Synthesize a minimal valid value for a JSON schema node."""
    schema = resolve_schema(spec, schema)
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if "anyOf" in schema or "oneOf" in schema:
        opts = schema.get("anyOf") or schema.get("oneOf")
        non_null = [o for o in opts if resolve_schema(spec, o).get("type") != "null"]
        return sample(spec, (non_null or opts)[0], ids, depth)
    t = schema.get("type")
    if t == "object" or "properties" in schema:
        props = schema.get("properties", {})
        required = schema.get("required", list(props.keys()))
        out = {}
        for k, v in props.items():
            if k in required:
                out[k] = field_value(spec, k, v, ids, depth)
        return out
    if t == "array":
        item = sample(spec, schema.get("items", {"type": "string"}), ids, depth + 1)
        return [item]
    if t == "integer":
        return 1
    if t == "number":
        return 1.0
    if t == "boolean":
        return False
    return "probe"


def field_value(spec, name, schema, ids, depth):
    """Field-name-aware value (dates, emails, ids) on top of type-based defaults."""
    rs = resolve_schema(spec, schema)
    low = name.lower()
    fmt = rs.get("format", "")
    if "email" in low:
        return "probe.user@example.com"
    if low.endswith("_id") or low == "id":
        key = low
        if key in ids:
            return ids[key]
        return ids.get("user_id", "00000000-0000-0000-0000-000000000000")
    if "start_date" in low:
        return (date.today() + timedelta(days=10)).isoformat()
    if "end_date" in low:
        return (date.today() + timedelta(days=11)).isoformat()
    if fmt == "date":
        return date.today().isoformat()
    if fmt == "date-time":
        return (date.today()).isoformat() + "T09:00:00"
    if "rating" in low or "score" in low:
        return 5
    return sample(spec, schema, ids, depth + 1)


def main():
    hr = login("hr1@mark.ai")
    emp = login("emp1@mark.ai")
    with urllib.request.urlopen(f"{BASE}/openapi.json", timeout=10) as r:
        spec = json.load(r)

    # Gather live IDs.
    ids = {}
    _, users = req("GET", "/api/v1/users", token=hr)
    if isinstance(users, list) and users:
        ids["user_id"] = next((u["id"] for u in users if u.get("role") == "employee"), users[0]["id"])
        ids["to_user_id"] = next((u["id"] for u in users if u.get("role") == "hr"), users[0]["id"])
        ids["buddy_id"] = users[0]["id"]
        ids["assignee_id"] = ids["to_user_id"]
    for path, key in [("/api/v1/tickets", "ticket_id"), ("/api/v1/surveys", "survey_id")]:
        _, rows = req("GET", path, token=hr)
        if isinstance(rows, list) and rows:
            ids[key] = rows[0]["id"]

    rows = []
    for path, ops in sorted(spec["paths"].items()):
        for method in ("post", "patch", "put"):
            if method not in ops:
                continue
            if path in SKIP:
                rows.append(("skip", method.upper(), path, SKIP[path]))
                continue
            op = ops[method]
            body = None
            rb = op.get("requestBody")
            if rb:
                content = rb.get("content", {}).get("application/json", {})
                if "schema" in content:
                    body = sample(spec, content["schema"], ids)
            filled = path
            missing = False
            for p in re.findall(r"\{([^}]+)\}", path):
                if p in ids:
                    filled = filled.replace(f"{{{p}}}", str(ids[p]))
                else:
                    missing = True
            if missing:
                rows.append(("skip", method.upper(), path, "no live id for path param"))
                continue
            # HR token first; retry as employee on 401/403.
            st, payload = req(method.upper(), filled, body, hr)
            if st in (401, 403):
                st, payload = req(method.upper(), filled, body, emp)
            detail = ""
            if st >= 400:
                detail = (payload or {}).get("detail") if isinstance(payload, dict) else payload
            rows.append((st, method.upper(), path, str(detail)[:150]))

    ok = [r for r in rows if isinstance(r[0], int) and r[0] < 400]
    err5 = [r for r in rows if isinstance(r[0], int) and r[0] >= 500]
    err4 = [r for r in rows if isinstance(r[0], int) and 400 <= r[0] < 500]
    skipped = [r for r in rows if r[0] == "skip"]
    print(f"Functional probe: {len(ok)} ok · {len(err4)} 4xx · {len(err5)} 5xx · {len(skipped)} skipped")
    if err5:
        print("\n=== 5xx (server errors) ===")
        for st, m, p, d in err5:
            print(f"  [{st}] {m} {p}\n        {d}")
    if err4:
        print("\n=== 4xx on schema-valid payload (review) ===")
        for st, m, p, d in err4:
            print(f"  [{st}] {m} {p}\n        {d}")
    return 1 if err5 else 0


if __name__ == "__main__":
    raise SystemExit(main())
