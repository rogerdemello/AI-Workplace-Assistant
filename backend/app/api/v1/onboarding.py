from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from ...database import get_db
from ...auth import get_current_user
from ...models.user import User
from ...models.onboarding_checklist import OnboardingChecklist

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingTaskResponse(BaseModel):
    id: UUID
    user_id: UUID
    task_name: str
    task_description: Optional[str]
    is_completed: bool
    completed_at: Optional[datetime]
    due_date: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OnboardingTaskUpdate(BaseModel):
    is_completed: bool


class UserChecklistResponse(BaseModel):
    user_id: UUID
    tasks: List[OnboardingTaskResponse]
    completed_count: int
    total_count: int


def get_db_session(db: Session = Depends(get_db)) -> Session:
    return db


@router.get("/{user_id}", response_model=UserChecklistResponse)
def get_user_checklist(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get onboarding checklist for a user."""
    # Users can only view their own checklist, HR/Admin can view any
    if current_user.id != user_id and current_user.role not in ["hr", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own checklist"
        )

    tasks = db.query(OnboardingChecklist).filter(
        OnboardingChecklist.user_id == user_id
    ).all()

    completed_count = sum(1 for t in tasks if t.is_completed)
    total_count = len(tasks)

    return UserChecklistResponse(
        user_id=user_id,
        tasks=[
            OnboardingTaskResponse(
                id=task.id,
                user_id=task.user_id,
                task_name=task.task_name,
                task_description=task.task_description,
                is_completed=task.is_completed,
                completed_at=task.completed_at,
                due_date=task.due_date,
                created_at=task.created_at,
            )
            for task in tasks
        ],
        completed_count=completed_count,
        total_count=total_count,
    )


@router.patch("/{task_id}", response_model=OnboardingTaskResponse)
def update_task(
    task_id: UUID,
    task_update: OnboardingTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a task as completed or incomplete."""
    task = db.query(OnboardingChecklist).filter(
        OnboardingChecklist.id == task_id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Users can only update their own tasks, HR/Admin can update any
    if current_user.id != task.user_id and current_user.role not in ["hr", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own tasks"
        )

    task.is_completed = task_update.is_completed
    if task_update.is_completed:
        task.completed_at = datetime.utcnow()
    else:
        task.completed_at = None

    db.commit()
    db.refresh(task)

    return OnboardingTaskResponse(
        id=task.id,
        user_id=task.user_id,
        task_name=task.task_name,
        task_description=task.task_description,
        is_completed=task.is_completed,
        completed_at=task.completed_at,
        due_date=task.due_date,
        created_at=task.created_at,
    )