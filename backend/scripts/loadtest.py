"""Concurrent load probe for the chat and HR-analytics paths.

task.txt item C asks for load testing under expected concurrent users. This is
the harness; the numbers have to come from an environment that resembles
production. Run it against staging, not your laptop — a local SQLite backend
tells you about SQLite, not about the deployment.

What it drives, because these are the paths that actually carry load:
  * POST /api/v1/chat/message      — the employee hot path (LLM + sentiment)
  * GET  /api/v1/analytics/dashboard — the HR read that fans out over the org
  * GET  /api/v1/requests          — the HR work queue

Usage::

    python -m scripts.loadtest --base-url https://staging.example.com \\
        --employees 25 --hr 5 --duration 60

Authentication uses the seeded demo accounts by default (see
scripts/seed_dummy_users.py); override with --employee-email / --hr-email.

Reported per endpoint: request count, error count, throughput, and p50/p95/p99
latency. Percentiles are computed from every sample held in memory, so keep
--duration sane for very high concurrency.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

DEFAULT_PASSWORD = "password123"

EMPLOYEE_MESSAGES = [
    "hey, how are things looking this week?",
    "I want to apply for leave",
    "what is the remote work policy?",
    "I need my payslip",
    "feeling a bit stretched lately",
    "can I book an appointment with HR?",
]


@dataclass
class Results:
    latencies: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    statuses: Dict[str, Dict[int, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )

    def record(self, label: str, seconds: float, status: Optional[int]) -> None:
        self.latencies[label].append(seconds)
        if status is None:
            self.errors[label] += 1
        else:
            self.statuses[label][status] += 1
            if status >= 400:
                self.errors[label] += 1


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]


async def _login(client: httpx.AsyncClient, base_url: str, email: str, password: str) -> Optional[str]:
    try:
        response = await client.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=30.0,
        )
        if response.status_code != 200:
            print(f"  login failed for {email}: HTTP {response.status_code}", file=sys.stderr)
            return None
        return response.json().get("access_token")
    except Exception as exc:
        print(f"  login error for {email}: {exc}", file=sys.stderr)
        return None


async def _timed(
    client: httpx.AsyncClient,
    results: Results,
    label: str,
    method: str,
    url: str,
    **kwargs,
) -> None:
    started = time.perf_counter()
    status: Optional[int] = None
    try:
        response = await client.request(method, url, **kwargs)
        status = response.status_code
    except Exception:
        status = None
    finally:
        results.record(label, time.perf_counter() - started, status)


async def _employee_loop(
    base_url: str, token: str, deadline: float, results: Results, think_time: float
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        conversation_id: Optional[str] = None
        while time.monotonic() < deadline:
            payload: Dict[str, object] = {"message": random.choice(EMPLOYEE_MESSAGES)}
            if conversation_id:
                payload["conversation_id"] = conversation_id
            started = time.perf_counter()
            status: Optional[int] = None
            try:
                response = await client.post(
                    f"{base_url}/api/v1/chat/message", json=payload, headers=headers
                )
                status = response.status_code
                if status == 200:
                    conversation_id = response.json().get("conversation_id") or conversation_id
            except Exception:
                status = None
            finally:
                results.record("POST /chat/message", time.perf_counter() - started, status)
            await asyncio.sleep(think_time)


async def _hr_loop(
    base_url: str, token: str, deadline: float, results: Results, think_time: float
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        while time.monotonic() < deadline:
            await _timed(
                client,
                results,
                "GET /analytics/dashboard",
                "GET",
                f"{base_url}/api/v1/analytics/dashboard",
                headers=headers,
            )
            await _timed(
                client,
                results,
                "GET /requests",
                "GET",
                f"{base_url}/api/v1/requests",
                headers=headers,
            )
            await asyncio.sleep(think_time)


def _report(results: Results, wall_seconds: float) -> int:
    print(f"\n{'endpoint':<28} {'reqs':>7} {'err':>6} {'rps':>8} "
          f"{'p50':>8} {'p95':>8} {'p99':>8} {'max':>8}")
    print("-" * 86)

    total_errors = 0
    for label in sorted(results.latencies):
        samples = results.latencies[label]
        errors = results.errors[label]
        total_errors += errors
        print(
            f"{label:<28} {len(samples):>7} {errors:>6} "
            f"{len(samples) / wall_seconds:>8.1f} "
            f"{_percentile(samples, 50) * 1000:>7.0f}ms "
            f"{_percentile(samples, 95) * 1000:>7.0f}ms "
            f"{_percentile(samples, 99) * 1000:>7.0f}ms "
            f"{max(samples) * 1000:>7.0f}ms"
        )

    for label in sorted(results.statuses):
        codes = ", ".join(f"{code}:{n}" for code, n in sorted(results.statuses[label].items()))
        print(f"  {label} status codes -> {codes}")

    print(f"\nwall time {wall_seconds:.1f}s, total errors {total_errors}")
    if total_errors:
        print("FAIL: errors occurred under load", file=sys.stderr)
        return 1
    print("OK: no errors under load")
    return 0


async def _run(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    results = Results()

    print(f"Authenticating {args.employees} employee + {args.hr} HR sessions against {base_url}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        employee_token = await _login(client, base_url, args.employee_email, args.password)
        hr_token = await _login(client, base_url, args.hr_email, args.password) if args.hr else None

    if args.employees and not employee_token:
        print("Cannot run: employee login failed. Seed demo users first.", file=sys.stderr)
        return 2
    if args.hr and not hr_token:
        print("Cannot run: HR login failed. Seed demo users first.", file=sys.stderr)
        return 2

    # Every virtual user shares a token but runs its own client and conversation.
    # That models concurrency, not distinct accounts — note it when reading results.
    deadline = time.monotonic() + args.duration
    tasks = [
        _employee_loop(base_url, employee_token, deadline, results, args.think_time)
        for _ in range(args.employees)
    ] + [
        _hr_loop(base_url, hr_token, deadline, results, args.think_time)
        for _ in range(args.hr)
    ]

    print(f"Running {len(tasks)} virtual users for {args.duration}s...")
    started = time.monotonic()
    await asyncio.gather(*tasks, return_exceptions=True)
    return _report(results, time.monotonic() - started)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--employees", type=int, default=10, help="concurrent employee chat users")
    parser.add_argument("--hr", type=int, default=2, help="concurrent HR dashboard users")
    parser.add_argument("--duration", type=int, default=30, help="seconds to sustain load")
    parser.add_argument("--think-time", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--employee-email", default="emp1@mark.ai")
    parser.add_argument("--hr-email", default="hr1@mark.ai")
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    args = parser.parse_args()

    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
