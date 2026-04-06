"""
Create two simulation users in the app database (SQLAlchemy / same DB as FastAPI).

  - HR:     hr@mark.ai       / password123
  - Employee: employee@mark.ai / password123

Run from the `backend` directory:

  python -m scripts.seed_dummy_users

Idempotent: safe to run multiple times (updates password/role if emails already exist).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Resolve package root (backend/)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import app.models  # noqa: F401 — register all models with Base.metadata
from app.auth.password import hash_password
from app.database import Base, SessionLocal, engine
from app.models.user import User, UserRole, UserStatus


DUMMY_USERS: tuple[tuple[str, str, str, UserRole, str], ...] = (
    ("hr@mark.ai", "HR Demo", "EMP-HR-001", UserRole.hr, "HR Business Partner"),
    ("employee@mark.ai", "Employee Demo", "EMP-001", UserRole.employee, "Software Engineer"),
)

DEFAULT_PASSWORD = "password123"


def ensure_tables() -> None:
    Base.metadata.create_all(bind=engine)


def seed() -> None:
    ensure_tables()
    db = SessionLocal()
    try:
        for email, name, employee_id, role, designation in DUMMY_USERS:
            existing = db.query(User).filter(User.email == email).first()
            pwd = hash_password(DEFAULT_PASSWORD)
            if existing:
                existing.name = name
                existing.employee_id = employee_id
                existing.role = role
                existing.designation = designation
                existing.status = UserStatus.active
                existing.hashed_password = pwd
                print(f"Updated: {email} ({role.value})")
            else:
                user = User(
                    email=email,
                    name=name,
                    employee_id=employee_id,
                    hashed_password=pwd,
                    role=role,
                    designation=designation,
                    status=UserStatus.active,
                )
                db.add(user)
                print(f"Created: {email} ({role.value})")
        db.commit()
        print("\nDone. Use these to sign in (and syncBackendAuthToken will match the API):")
        print("  HR:       hr@mark.ai       / " + DEFAULT_PASSWORD)
        print("  Employee: employee@mark.ai / " + DEFAULT_PASSWORD)
    except Exception as e:
        db.rollback()
        print(f"Error: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
