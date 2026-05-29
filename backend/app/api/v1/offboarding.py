"""Offboarding clearance + knowledge-transfer task endpoints."""

from __future__ import annotations

from datetime import date as _date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..database import get_db
from ..core.time import utcnow_naive
from ..models.offboarding_task import OffboardingTask, TASK_KINDS
from ..models.user import User
from ..services.offboarding import (
    list_tasks_for_user,
    seed_canonical_offboarding_tasks,
)


router = APIRouter(tags=["offboarding"])


class OffboardingTaskOut(BaseModel):
    id: str
    user_id: str
    title: str
    kind: str
    completed: bool
    completed_at: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None


class OffboardingTaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    kind: str = Field("custom")
    due_date: Optional[_date] = None
    notes: Optional[str] = None
    assigned_to: Optional[UUID] = None


class OffboardingTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    kind: Optional[str] = None
    completed: Optional[bool] = None
    due_date: Optional[_date] = None
    notes: Optional[str] = None
    assigned_to: Optional[UUID] = None


def _to_out(t: OffboardingTask) -> OffboardingTaskOut:
    return OffboardingTaskOut(
        id=str(t.id),
        user_id=str(t.user_id),
        title=t.title,
        kind=t.kind,
        completed=bool(t.completed),
        completed_at=t.completed_at.isoformat() if t.completed_at else None,
        due_date=t.due_date.isoformat() if t.due_date else None,
        notes=t.notes,
        assigned_to=str(t.assigned_to) if t.assigned_to else None,
    )


def _can_view(target_id: UUID, current: User) -> bool:
    if current.id == target_id:
        return True
    role = current.role.value if hasattr(current.role, "value") else str(current.role)
    return role in ("hr", "admin")


def _can_manage(current: User) -> bool:
    role = current.role.value if hasattr(current.role, "value") else str(current.role)
    return role in ("hr", "admin")


@router.get("/users/{user_id}/offboarding-tasks", response_model=List[OffboardingTaskOut])
def get_offboarding_tasks(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List clearance / KT tasks. Auto-seeds the canonical set the first time
    this is called for a user whose departure_at is set.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not _can_view(user_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    if user.departure_at is not None:
        seed_canonical_offboarding_tasks(db, user)

    return [_to_out(t) for t in list_tasks_for_user(db, user_id)]


@router.post(
    "/users/{user_id}/offboarding-tasks",
    response_model=OffboardingTaskOut,
    status_code=status.HTTP_201_CREATED,
)
def create_offboarding_task(
    user_id: UUID,
    payload: OffboardingTaskCreate,
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    """HR/admin: add a custom clearance or KT task to a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    kind = payload.kind if payload.kind in TASK_KINDS else "custom"
    t = OffboardingTask(
        user_id=user_id,
        title=payload.title.strip(),
        kind=kind,
        due_date=payload.due_date,
        notes=(payload.notes or "").strip() or None,
        assigned_to=payload.assigned_to,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_out(t)


@router.patch("/offboarding-tasks/{task_id}", response_model=OffboardingTaskOut)
def update_offboarding_task(
    task_id: UUID,
    payload: OffboardingTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a task complete or edit it. Self can complete their own tasks; HR
    can edit any field; assignees can complete tasks routed to them."""
    t = db.query(OffboardingTask).filter(OffboardingTask.id == task_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    is_owner = current_user.id == t.user_id
    is_assignee = t.assigned_to is not None and current_user.id == t.assigned_to
    is_hr = _can_manage(current_user)
    if not (is_owner or is_assignee or is_hr):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    # Self / assignee can only flip completion (and tweak notes); HR can edit all.
    if payload.completed is not None:
        if payload.completed and not t.completed:
            t.completed = True
            t.completed_at = utcnow_naive()
        elif not payload.completed and t.completed:
            t.completed = False
            t.completed_at = None
    if payload.notes is not None and (is_hr or is_owner or is_assignee):
        t.notes = payload.notes.strip() or None
    if is_hr:
        if payload.title is not None:
            t.title = payload.title.strip()
        if payload.kind is not None and payload.kind in TASK_KINDS:
            t.kind = payload.kind
        if payload.due_date is not None:
            t.due_date = payload.due_date
        if payload.assigned_to is not None:
            t.assigned_to = payload.assigned_to

    db.commit()
    db.refresh(t)
    return _to_out(t)


@router.delete("/offboarding-tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_offboarding_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    t = db.query(OffboardingTask).filter(OffboardingTask.id == task_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    db.delete(t)
    db.commit()
    return None
