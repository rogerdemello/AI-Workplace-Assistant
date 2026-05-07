from __future__ import annotations

import json
import hashlib
import urllib.request
from dataclasses import dataclass


@dataclass
class ProviderSyncResult:
    records_seen: int
    records_changed: int
    details: str


class ProviderSyncService:
    """Executes lightweight live sync calls for configured providers."""
    _last_snapshot_hash: dict[str, str] = {}

    def _request_json(self, url: str, token: str, timeout_seconds: int = 15) -> dict:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
        return json.loads(body) if body else {}

    def run_hrms_sync(self, *, base_url: str, api_token: str, dry_run: bool) -> ProviderSyncResult:
        payload = self._request_json(f"{base_url.rstrip('/')}/employees", api_token)
        employees = payload.get("employees") if isinstance(payload, dict) else []
        seen = len(employees) if isinstance(employees, list) else 0
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        previous_hash = self._last_snapshot_hash.get(f"{base_url}|hrms")
        changed = 0 if dry_run or previous_hash == payload_hash else seen
        self._last_snapshot_hash[f"{base_url}|hrms"] = payload_hash
        details = "Live HRMS sync executed." if not dry_run else "Live HRMS dry run executed."
        if previous_hash == payload_hash:
            details += " No upstream delta detected."
        return ProviderSyncResult(records_seen=seen, records_changed=changed, details=details)

    def run_payroll_sync(self, *, base_url: str, api_token: str, dry_run: bool) -> ProviderSyncResult:
        payload = self._request_json(f"{base_url.rstrip('/')}/payroll-runs", api_token)
        runs = payload.get("runs") if isinstance(payload, dict) else []
        seen = len(runs) if isinstance(runs, list) else 0
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        previous_hash = self._last_snapshot_hash.get(f"{base_url}|payroll")
        changed = 0 if dry_run or previous_hash == payload_hash else seen
        self._last_snapshot_hash[f"{base_url}|payroll"] = payload_hash
        details = "Live payroll sync executed." if not dry_run else "Live payroll dry run executed."
        if previous_hash == payload_hash:
            details += " No upstream delta detected."
        return ProviderSyncResult(records_seen=seen, records_changed=changed, details=details)

