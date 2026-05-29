"""Canonical offboarding tasks + seeding helper.

Seeded once per (user, kind:title) when departure_at is first set. Idempotent —
calling seed_for_user a second time after some tasks have been completed won't
re-create the canonical ones (so completion state is preserved).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.offboarding_task import OffboardingTask
from ..models.user import User


# (kind, title, days_before_departure). due_date is computed from User.departure_at.
_CANONICAL_TASKS: List[tuple[str, str, int]] = [
    ("handover", "Hand off active projects to a teammate", 14),
    ("kt", "Write a knowledge-transfer doc for the team", 14),
    ("handover", "Notify direct stakeholders of departure", 14),
    ("kt", "Final code reviews / pending merges", 7),
    ("clearance", "Submit pending timesheets / expenses", 5),
    ("clearance", "Return laptop and access cards", 1),
    ("clearance", "Revoke external tool access (HR-side)", 1),
    ("exit", "Complete exit interview survey", 0),
]


def seed_canonical_offboarding_tasks(db: Session, user: User) -> int:
    """Create the canonical tasks for a departing user, skipping any already
    present (matched by kind + title). Returns the number of new rows added.
    """
    if not user or user.departure_at is None:
        return 0

    departure_date = user.departure_at.date() if hasattr(user.departure_at, "date") else user.departure_at
    if not isinstance(departure_date, date):
        return 0

    existing = (
        db.query(OffboardingTask.kind, OffboardingTask.title)
        .filter(OffboardingTask.user_id == user.id)
        .all()
    )
    existing_keys = {(row.kind, row.title) for row in existing}

    added = 0
    for kind, title, days_before in _CANONICAL_TASKS:
        key = (kind, title)
        if key in existing_keys:
            continue
        due = departure_date - timedelta(days=max(0, days_before))
        db.add(
            OffboardingTask(
                user_id=user.id,
                title=title,
                kind=kind,
                due_date=due,
                completed=False,
            )
        )
        added += 1

    if added:
        db.commit()
    return added


def list_tasks_for_user(db: Session, user_id: UUID) -> List[OffboardingTask]:
    """Return tasks ordered: incomplete first, then by due_date / created_at."""
    return (
        db.query(OffboardingTask)
        .filter(OffboardingTask.user_id == user_id)
        .order_by(
            OffboardingTask.completed.asc(),
            OffboardingTask.due_date.asc().nullslast(),
            OffboardingTask.created_at.asc(),
        )
        .all()
    )
