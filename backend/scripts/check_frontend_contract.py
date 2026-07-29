#!/usr/bin/env python3
"""Cross-check: every backend path the frontend calls must exist on the backend.

Scans the frontend source for /api/v1/* and /hr/* path literals (including
template-literal params), normalizes them, and matches against the live
OpenAPI spec. Frontend calls with no backend route are flagged as broken
workflows. Run with the backend up on :8099.
"""
from __future__ import annotations
import json, re, sys, urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "new-frontend" / "src"
BASE = "http://127.0.0.1:8099"

# Match string/template literals starting with /api/v1 or /hr.
PATH_RE = re.compile(r"""["'`](/(?:api/v1|hr)/[^"'`\s]*)["'`]""")


def normalize(path: str) -> str:
    path = path.split("?")[0].split("#")[0]
    path = re.sub(r"\$\{[^}]*\}", "{}", path)   # template params -> {}
    path = re.sub(r"`\s*\+\s*[^/]*", "{}", path)  # crude concat tail
    return path.rstrip("/") or "/"


def to_segments(p: str):
    return [s for s in p.strip("/").split("/") if s != ""]


def matches(fe: str, be: str) -> bool:
    fs, bs = to_segments(fe), to_segments(be)
    if len(fs) != len(bs):
        return False
    for f, b in zip(fs, bs):
        if b.startswith("{") and b.endswith("}"):
            continue          # backend path param — matches anything
        if f == "{}":
            continue          # frontend template param — matches anything
        if f != b:
            return False
    return True


def main():
    spec = json.load(urllib.request.urlopen(f"{BASE}/openapi.json", timeout=10))
    be_paths = list(spec["paths"].keys())

    found = {}
    for f in list(FRONTEND.rglob("*.ts")) + list(FRONTEND.rglob("*.tsx")):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in PATH_RE.findall(text):
            norm = normalize(m)
            found.setdefault(norm, set()).add(f.name)

    missing = []
    ok = 0
    for fe in sorted(found):
        if any(matches(fe, be) for be in be_paths):
            ok += 1
        else:
            missing.append((fe, sorted(found[fe])))

    print(f"Frontend->backend contract: {ok} matched, {len(missing)} UNMATCHED of {len(found)} distinct paths")
    if missing:
        print("\n=== UNMATCHED (frontend calls a path with no backend route) ===")
        for fe, files in missing:
            print(f"  {fe}\n      used in: {', '.join(files)}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
