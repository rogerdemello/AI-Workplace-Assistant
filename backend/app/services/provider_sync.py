from __future__ import annotations

import hashlib
import json
import secrets
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..auth import hash_password
from ..models.department import Department
from ..models.user import User, UserRole, UserStatus


@dataclass
class ProviderSyncResult:
    records_seen: int
    records_changed: int
    details: str


def _first(record: dict, *keys: str) -> Optional[str]:
    """Return the first non-empty string value across candidate keys."""
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_employee(record: dict) -> Optional[dict]:
    """Map a provider employee payload onto MARK's user fields.

    Providers differ (Workday vs SAP SuccessFactors vs others), so we probe the
    common field-name variants. Returns None when there is no usable email — we
    key the org chart on email and skip records we can't anchor.
    """
    if not isinstance(record, dict):
        return None
    email = _first(record, "email", "workEmail", "primaryWorkEmail", "emailAddress", "work_email")
    if not email:
        return None
    name = _first(record, "name", "displayName", "fullName", "full_name")
    if not name:
        first = _first(record, "firstName", "first_name", "givenName") or ""
        last = _first(record, "lastName", "last_name", "familyName") or ""
        name = f"{first} {last}".strip() or email.split("@")[0]
    raw_status = record.get("status") or record.get("employmentStatus") or record.get("active")
    if isinstance(raw_status, bool):
        active = raw_status
    else:
        active = str(raw_status or "active").strip().lower() not in (
            "inactive", "terminated", "terminate", "left", "exited", "false", "0",
        )
    return {
        "email": email.lower(),
        "name": name,
        "employee_id": _first(record, "employeeId", "employee_id", "associateOID", "personId"),
        "designation": _first(record, "title", "jobTitle", "job_title", "designation", "position"),
        "department": _first(record, "department", "departmentName", "orgUnit", "division"),
        "active": active,
    }


class ProviderSyncService:
    """Executes live sync calls for configured HRMS / payroll providers.

    HRMS sync upserts the provider's org chart into the local ``users`` table
    (the directory other MARK surfaces read from). Payroll sync surfaces a
    summary of the latest runs — MARK has no payroll table to persist into, so
    that path stays read-only by design.
    """

    _last_snapshot_hash: dict[str, str] = {}

    def _request_json(self, url: str, token: str, timeout_seconds: int = 15) -> Any:
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

    def _resolve_department_id(self, db: Session, name: Optional[str], cache: dict[str, Any]):
        if not name:
            return None
        key = name.strip().lower()
        if key in cache:
            return cache[key]
        dept = db.query(Department).filter(Department.name.ilike(name.strip())).first()
        if not dept:
            dept = Department(name=name.strip())
            db.add(dept)
            db.flush()  # assign PK without a full commit
        cache[key] = dept.id
        return dept.id

    def _upsert_employees(self, db: Session, employees: list[dict]) -> int:
        """Create/update users from normalized provider records. Returns count changed."""
        changed = 0
        dept_cache: dict[str, Any] = {}
        for raw in employees:
            norm = _normalize_employee(raw)
            if not norm:
                continue
            user = db.query(User).filter(User.email == norm["email"]).first()
            target_status = UserStatus.active if norm["active"] else UserStatus.inactive
            dept_id = self._resolve_department_id(db, norm["department"], dept_cache)
            if user:
                dirty = False
                if norm["name"] and user.name != norm["name"]:
                    user.name = norm["name"]; dirty = True
                if norm["designation"] and user.designation != norm["designation"]:
                    user.designation = norm["designation"]; dirty = True
                if norm["employee_id"] and user.employee_id != norm["employee_id"]:
                    user.employee_id = norm["employee_id"]; dirty = True
                if dept_id is not None and user.department_id != dept_id:
                    user.department_id = dept_id; dirty = True
                if user.status != target_status:
                    user.status = target_status; dirty = True
                if dirty:
                    db.add(user)
                    changed += 1
            else:
                db.add(User(
                    name=norm["name"],
                    email=norm["email"],
                    hashed_password=hash_password(secrets.token_urlsafe(12)),
                    role=UserRole.employee,
                    designation=norm["designation"],
                    employee_id=norm["employee_id"],
                    department_id=dept_id,
                    status=target_status,
                ))
                changed += 1
        return changed

    def run_hrms_sync(
        self,
        *,
        base_url: str,
        api_token: str,
        dry_run: bool,
        db: Optional[Session] = None,
    ) -> ProviderSyncResult:
        payload = self._request_json(f"{base_url.rstrip('/')}/employees", api_token)
        employees = payload.get("employees") if isinstance(payload, dict) else payload
        if not isinstance(employees, list):
            employees = []
        seen = len(employees)
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        previous_hash = self._last_snapshot_hash.get(f"{base_url}|hrms")
        no_delta = previous_hash == payload_hash

        if dry_run or db is None:
            changed = 0
            details = "Live HRMS dry run executed." if dry_run else "Live HRMS sync executed (no DB session — counted only)."
        else:
            changed = self._upsert_employees(db, employees)
            db.commit()
            details = f"Live HRMS sync executed. Upserted {changed} employee record(s) into the directory."

        self._last_snapshot_hash[f"{base_url}|hrms"] = payload_hash
        if no_delta:
            details += " No upstream delta detected."
        return ProviderSyncResult(records_seen=seen, records_changed=changed, details=details)

    def run_payroll_sync(
        self,
        *,
        base_url: str,
        api_token: str,
        dry_run: bool,
        db: Optional[Session] = None,
    ) -> ProviderSyncResult:
        payload = self._request_json(f"{base_url.rstrip('/')}/payroll-runs", api_token)
        runs = payload.get("runs") if isinstance(payload, dict) else payload
        if not isinstance(runs, list):
            runs = []
        seen = len(runs)
        total_gross = 0.0
        for run in runs:
            if isinstance(run, dict):
                try:
                    total_gross += float(run.get("gross") or run.get("grossAmount") or run.get("amount") or 0)
                except (TypeError, ValueError):
                    pass
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        previous_hash = self._last_snapshot_hash.get(f"{base_url}|payroll")
        no_delta = previous_hash == payload_hash
        changed = 0 if (dry_run or no_delta) else seen
        self._last_snapshot_hash[f"{base_url}|payroll"] = payload_hash
        details = (
            f"Live payroll {'dry run' if dry_run else 'sync'} executed. "
            f"{seen} run(s) seen, gross total {total_gross:,.2f}."
        )
        if no_delta:
            details += " No upstream delta detected."
        return ProviderSyncResult(records_seen=seen, records_changed=changed, details=details)
