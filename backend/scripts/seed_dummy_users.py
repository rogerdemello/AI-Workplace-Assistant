"""
Create deterministic demo users in the app database (SQLAlchemy / same DB as FastAPI).

  - HR:        hr1@infeedo.ai         / password123
  - Manager:   manager1@infeedo.ai   / password123 (optional if DB enum supports manager)
  - Employee:  employee1@infeedo.ai  / password123

Run from the `backend` directory:

  python -m scripts.seed_dummy_users

Idempotent: safe to run multiple times (updates passwords, roles, org links).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Resolve package root (backend/)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import app.models  # noqa: F401 — register all models with Base.metadata
from sqlalchemy.exc import DataError

from app.auth.password import hash_password
from app.database import Base, SessionLocal, engine
from app.models.department import Department
from app.models.user import User, UserRole, UserStatus

CORE_USERS: tuple[tuple[str, str, str, UserRole, str], ...] = (
    ("hr1@infeedo.ai", "HR One", "HR-1", UserRole.hr, "HR Business Partner"),
    ("employee1@infeedo.ai", "Employee One", "EMP-1", UserRole.employee, "Team Member"),
)

MANAGER_ROW = ("manager1@infeedo.ai", "Manager One", "MGR-1", UserRole.manager, "Engineering Manager")

DEFAULT_PASSWORD = "password123"


def ensure_tables() -> None:
    Base.metadata.create_all(bind=engine)


def _ensure_department(db) -> Department:
    dept = db.query(Department).filter(Department.name == "General").first()
    if dept:
        return dept
    dept = Department(name="General", description="Default department for seed users")
    db.add(dept)
    db.flush()
    return dept


def _upsert_user(db, email: str, name: str, employee_id: str, role: UserRole, designation: str, **kwargs) -> User:
    existing = db.query(User).filter(User.email == email).first()
    pwd = hash_password(DEFAULT_PASSWORD)
    if existing:
        existing.name = name
        existing.employee_id = employee_id
        existing.role = role
        existing.designation = designation
        existing.status = UserStatus.active
        existing.hashed_password = pwd
        for key, value in kwargs.items():
            setattr(existing, key, value)
        return existing
    user = User(
        email=email,
        name=name,
        employee_id=employee_id,
        hashed_password=pwd,
        role=role,
        designation=designation,
        status=UserStatus.active,
        **kwargs,
    )
    db.add(user)
    db.flush()
    return user


def seed() -> None:
    ensure_tables()
    db = SessionLocal()
    manager = None
    manager_supported = True
    try:
        dept = _ensure_department(db)
        mgr_email, mgr_name, mgr_eid, mgr_role, mgr_desig = MANAGER_ROW
        try:
            manager = _upsert_user(
                db,
                mgr_email,
                mgr_name,
                mgr_eid,
                mgr_role,
                mgr_desig,
                department_id=dept.id,
                manager_id=None,
            )
        except DataError as exc:
            db.rollback()
            manager_supported = False
            print(
                "Warning: DB enum userrole does not support 'manager' yet; skipping manager seed.",
                file=sys.stderr,
            )
            print(f"  Detail: {exc.orig}", file=sys.stderr)
            dept = _ensure_department(db)

        for email, name, employee_id, role, designation in CORE_USERS:
            extra: dict = {"department_id": dept.id}
            if email == "employee1@infeedo.ai":
                extra["manager_id"] = manager.id if manager is not None else None
            elif email == "hr1@infeedo.ai":
                extra["manager_id"] = None
            user = _upsert_user(db, email, name, employee_id, role, designation, **extra)
            print(f"OK: {user.email} ({user.role.value})")

        db.commit()
        print("\nDone. Sign in via POST /api/v1/auth/login:")
        print("  HR:        hr1@infeedo.ai         / " + DEFAULT_PASSWORD)
        if manager_supported and manager is not None:
            print("  Manager:   manager1@infeedo.ai   / " + DEFAULT_PASSWORD)
        print("  Employee:  employee1@infeedo.ai  / " + DEFAULT_PASSWORD)
    except Exception as e:
        db.rollback()
        print(f"Error: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
