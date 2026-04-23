from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from ...database import get_db
from ...auth import get_current_user
from ...models.user import User
from ...services.buddy_assignment_service import BuddyAssignmentService

router = APIRouter(prefix="/buddies", tags=["onboarding-buddies"])


class BuddyAssignmentResponse(BaseModel):
    id: UUID
    user_id: UUID
    buddy_id: UUID
    buddy_name: str
    buddy_email: str
    assigned_at: datetime
    active_until: Optional[datetime]
    is_active: bool
    notes: Optional[str]

    class Config:
        from_attributes = True


class BuddyAssignmentCreate(BaseModel):
    user_id: UUID
    buddy_id: Optional[UUID] = None
    notes: Optional[str] = None
    active_until: Optional[datetime] = None


class BuddyStatsResponse(BaseModel):
    active_assignments: int
    total_assignments: int
    max_capacity: int
    available_slots: int


class AvailableBuddyResponse(BaseModel):
    id: UUID
    name: str
    email: str
    department: Optional[str]
    designation: Optional[str]


@router.get("/me", response_model=BuddyAssignmentResponse)
def get_my_buddy(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = BuddyAssignmentService(db)
    assignment = service.get_active_buddy(current_user.id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active buddy assigned"
        )

    buddy = service.get_buddy_for_user(current_user.id)
    return BuddyAssignmentResponse(
        id=assignment.id,
        user_id=assignment.user_id,
        buddy_id=assignment.buddy_id,
        buddy_name=buddy.name if buddy else "Unknown",
        buddy_email=buddy.email if buddy else "",
        assigned_at=assignment.assigned_at,
        active_until=assignment.active_until,
        is_active=assignment.is_active,
        notes=assignment.notes
    )


@router.get("/stats", response_model=BuddyStatsResponse)
def get_my_buddy_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = BuddyAssignmentService(db)
    return service.get_buddy_stats(current_user.id)


@router.get("/user/{user_id}", response_model=BuddyAssignmentResponse)
def get_user_buddy(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["hr", "admin"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own buddy"
        )

    service = BuddyAssignmentService(db)
    assignment = service.get_active_buddy(user_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active buddy assigned"
        )

    buddy = service.get_buddy_for_user(user_id)
    return BuddyAssignmentResponse(
        id=assignment.id,
        user_id=assignment.user_id,
        buddy_id=assignment.buddy_id,
        buddy_name=buddy.name if buddy else "Unknown",
        buddy_email=buddy.email if buddy else "",
        assigned_at=assignment.assigned_at,
        active_until=assignment.active_until,
        is_active=assignment.is_active,
        notes=assignment.notes
    )


@router.post("/assign", response_model=BuddyAssignmentResponse)
def assign_buddy(
    assignment_data: BuddyAssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR or admin can assign buddies"
        )

    service = BuddyAssignmentService(db)
    assignment = service.assign_buddy(
        user_id=assignment_data.user_id,
        buddy_id=assignment_data.buddy_id,
        assigned_by=current_user.id,
        notes=assignment_data.notes,
        active_until=assignment_data.active_until
    )

    buddy = service.get_buddy_for_user(assignment_data.user_id)
    return BuddyAssignmentResponse(
        id=assignment.id,
        user_id=assignment.user_id,
        buddy_id=assignment.buddy_id,
        buddy_name=buddy.name if buddy else "Unknown",
        buddy_email=buddy.email if buddy else "",
        assigned_at=assignment.assigned_at,
        active_until=assignment.active_until,
        is_active=assignment.is_active,
        notes=assignment.notes
    )


@router.post("/auto-assign/{user_id}", response_model=BuddyAssignmentResponse)
def auto_assign_buddy(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR or admin can auto-assign buddies"
        )

    service = BuddyAssignmentService(db)
    assignment = service.auto_assign_onboarding(user_id, current_user.id)

    buddy = service.get_buddy_for_user(user_id)
    return BuddyAssignmentResponse(
        id=assignment.id,
        user_id=assignment.user_id,
        buddy_id=assignment.buddy_id,
        buddy_name=buddy.name if buddy else "Unknown",
        buddy_email=buddy.email if buddy else "",
        assigned_at=assignment.assigned_at,
        active_until=assignment.active_until,
        is_active=assignment.is_active,
        notes=assignment.notes
    )


@router.get("/available", response_model=List[AvailableBuddyResponse])
def get_available_buddies(
    department: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR or admin can view available buddies"
        )

    service = BuddyAssignmentService(db)
    dept_id = None
    buddies = service.get_available_buddies(dept_id)
    return [
        AvailableBuddyResponse(
            id=b.id,
            name=b.name,
            email=b.email,
            department=b.department,
            designation=b.designation
        )
        for b in buddies
    ]