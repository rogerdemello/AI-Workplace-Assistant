"""Offboarding clearance + knowledge-transfer tasks for a departing employee."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from ..core.time import utcnow_naive
from ..database import Base


# Task "kind" — keeps clearance vs handover vs KT vs exit cleanly groupable on
# the frontend without an enum (kept as String so legacy environments don't need
# a Postgres enum to add a new bucket later).
TASK_KINDS = ("clearance", "handover", "kt", "exit", "custom")


class OffboardingTask(Base):
    __tablename__ = "offboarding_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    kind = Column(String(32), nullable=False, default="custom")
    completed = Column(Boolean, nullable=False, default=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    due_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow_naive)
    updated_at = Column(DateTime, nullable=False, default=utcnow_naive, onupdate=utcnow_naive)


# Speeds up "all tasks for this departing employee, completion-first".
Index("ix_offboarding_tasks_user_completed", OffboardingTask.user_id, OffboardingTask.completed)
