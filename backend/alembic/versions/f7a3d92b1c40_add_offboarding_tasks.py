"""Add offboarding_tasks for clearance + knowledge-transfer flows

Revision ID: f7a3d92b1c40
Revises: e1f2a3b4c5d6
Create Date: 2026-05-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "f7a3d92b1c40"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "offboarding_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="custom"),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "assigned_to",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_offboarding_tasks_user_id", "offboarding_tasks", ["user_id"])
    op.create_index("ix_offboarding_tasks_completed", "offboarding_tasks", ["completed"])
    op.create_index("ix_offboarding_tasks_assigned_to", "offboarding_tasks", ["assigned_to"])
    op.create_index(
        "ix_offboarding_tasks_user_completed",
        "offboarding_tasks",
        ["user_id", "completed"],
    )


def downgrade() -> None:
    op.drop_index("ix_offboarding_tasks_user_completed", table_name="offboarding_tasks")
    op.drop_index("ix_offboarding_tasks_assigned_to", table_name="offboarding_tasks")
    op.drop_index("ix_offboarding_tasks_completed", table_name="offboarding_tasks")
    op.drop_index("ix_offboarding_tasks_user_id", table_name="offboarding_tasks")
    op.drop_table("offboarding_tasks")
