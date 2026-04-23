from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models.user import User, UserStatus
from ..models.onboarding_buddy import OnboardingBuddy
from ..models.onboarding_checklist import OnboardingChecklist


class BuddyAssignmentService:
    DEFAULT_BUDDY_PERIOD_DAYS = 30
    MAX_ASSIGNMENTS_PER_BUDDY = 3

    def __init__(self, db: Session):
        self.db = db

    def get_active_buddy(self, user_id: UUID) -> Optional[OnboardingBuddy]:
        return self.db.query(OnboardingBuddy).filter(
            OnboardingBuddy.user_id == user_id,
            OnboardingBuddy.is_active == True
        ).first()

    def get_buddy_for_user(self, user_id: UUID) -> Optional[User]:
        assignment = self.get_active_buddy(user_id)
        if assignment:
            return self.db.query(User).filter(User.id == assignment.buddy_id).first()
        return None

    def get_available_buddies(self, department_id: Optional[UUID] = None) -> List[User]:
        subquery = self.db.query(OnboardingBuddy.buddy_id).filter(
            OnboardingBuddy.is_active == True,
            OnboardingBuddy.active_until > datetime.utcnow()
        ).subquery()

        query = self.db.query(User).filter(
            User.status == UserStatus.active,
            User.role.in_(["employee", "hr"]),
            User.id.notin_(subquery)
        )

        if department_id:
            query = query.filter(User.department_id == department_id)

        return query.limit(20).all()

    def assign_buddy(
        self,
        user_id: UUID,
        buddy_id: Optional[UUID] = None,
        assigned_by: Optional[UUID] = None,
        notes: Optional[str] = None,
        active_until: Optional[datetime] = None
    ) -> OnboardingBuddy:
        existing = self.get_active_buddy(user_id)
        if existing:
            existing.is_active = False
            existing.active_until = datetime.utcnow()

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        if buddy_id:
            buddy = self.db.query(User).filter(User.id == buddy_id).first()
            if not buddy:
                raise ValueError("Buddy not found")
        else:
            available = self.get_available_buddies(user.department_id)
            if not available:
                available = self.get_available_buddies()

            for candidate in available:
                current_count = self.db.query(OnboardingBuddy).filter(
                    OnboardingBuddy.buddy_id == candidate.id,
                    OnboardingBuddy.is_active == True,
                    OnboardingBuddy.active_until > datetime.utcnow()
                ).count()

                if current_count < self.MAX_ASSIGNMENTS_PER_BUDDY:
                    buddy = candidate
                    break
            else:
                buddy = available[0] if available else None

            if not buddy:
                raise ValueError("No available buddies found")
            buddy_id = buddy.id

        if not active_until:
            active_until = datetime.utcnow() + timedelta(days=self.DEFAULT_BUDDY_PERIOD_DAYS)

        assignment = OnboardingBuddy(
            user_id=user_id,
            buddy_id=buddy_id,
            assigned_by=assigned_by,
            notes=notes,
            active_until=active_until,
            is_active=True
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def create_default_checklist(self, user_id: UUID) -> List[OnboardingChecklist]:
        default_tasks = [
            ("Meet your buddy", "Connect with your assigned buddy for introductions"),
            ("Setup workspace", "Get your equipment and access credentials"),
            ("Complete HR paperwork", "Submit required documents"),
            ("Team introduction", "Meet your team members"),
            ("Review policies", "Read employee handbook"),
            ("First 1:1 with manager", "Schedule and complete first check-in"),
        ]
        tasks = []
        for task_name, task_description in default_tasks:
            task = OnboardingChecklist(
                user_id=user_id,
                task_name=task_name,
                task_description=task_description
            )
            self.db.add(task)
            tasks.append(task)

        self.db.commit()
        return tasks

    def get_buddy_stats(self, buddy_id: UUID) -> dict:
        active = self.db.query(OnboardingBuddy).filter(
            OnboardingBuddy.buddy_id == buddy_id,
            OnboardingBuddy.is_active == True,
            OnboardingBuddy.active_until > datetime.utcnow()
        ).count()

        total = self.db.query(OnboardingBuddy).filter(
            OnboardingBuddy.buddy_id == buddy_id
        ).count()

        return {
            "active_assignments": active,
            "total_assignments": total,
            "max_capacity": self.MAX_ASSIGNMENTS_PER_BUDDY,
            "available_slots": max(0, self.MAX_ASSIGNMENTS_PER_BUDDY - active)
        }

    def auto_assign_onboarding(self, user_id: UUID, assigned_by: Optional[UUID] = None) -> OnboardingBuddy:
        assignment = self.assign_buddy(user_id, assigned_by=assigned_by)
        self.create_default_checklist(user_id)
        return assignment


def get_user_buddy(db: Session, user_id: UUID) -> Optional[User]:
    service = BuddyAssignmentService(db)
    return service.get_buddy_for_user(user_id)


def auto_assign_buddy(db: Session, user_id: UUID, assigned_by: Optional[UUID] = None) -> OnboardingBuddy:
    service = BuddyAssignmentService(db)
    return service.auto_assign_onboarding(user_id, assigned_by)