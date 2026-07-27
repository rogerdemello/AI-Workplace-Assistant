"""Add employee_requests for chat-raised appointments, expenses, shift changes and documents

Revision ID: a4c8e17b2d59
Revises: f7a3d92b1c40
Create Date: 2026-07-27 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "a4c8e17b2d59"
down_revision = "f7a3d92b1c40"
branch_labels = None
depends_on = None


REQUEST_TYPES = ("appointment", "expense", "shift_change", "document")
REQUEST_STATUSES = (
    "pending",
    "scheduled",
    "approved",
    "rejected",
    "cancelled",
    "completed",
)


def upgrade() -> None:
    op.create_table(
        "employee_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("details", JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "handled_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
        sa.Column("hr_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "request_type IN ({})".format(", ".join(f"'{t}'" for t in REQUEST_TYPES)),
            name="ck_employee_requests_request_type",
        ),
        sa.CheckConstraint(
            "status IN ({})".format(", ".join(f"'{s}'" for s in REQUEST_STATUSES)),
            name="ck_employee_requests_status",
        ),
    )
    op.create_index("ix_employee_requests_user_id", "employee_requests", ["user_id"])
    op.create_index("ix_employee_requests_request_type", "employee_requests", ["request_type"])
    op.create_index("ix_employee_requests_status", "employee_requests", ["status"])
    op.create_index("ix_employee_requests_created_at", "employee_requests", ["created_at"])
    op.create_index("ix_employee_requests_scheduled_at", "employee_requests", ["scheduled_at"])
    op.create_index("ix_employee_requests_handled_by", "employee_requests", ["handled_by"])
    # HR's default view is "pending work, newest first".
    op.create_index(
        "ix_employee_requests_status_created_at",
        "employee_requests",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_employee_requests_status_created_at", table_name="employee_requests")
    op.drop_index("ix_employee_requests_handled_by", table_name="employee_requests")
    op.drop_index("ix_employee_requests_scheduled_at", table_name="employee_requests")
    op.drop_index("ix_employee_requests_created_at", table_name="employee_requests")
    op.drop_index("ix_employee_requests_status", table_name="employee_requests")
    op.drop_index("ix_employee_requests_request_type", table_name="employee_requests")
    op.drop_index("ix_employee_requests_user_id", table_name="employee_requests")
    op.drop_table("employee_requests")
