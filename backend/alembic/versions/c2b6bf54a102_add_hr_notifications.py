"""Add HR notifications table

Revision ID: c2b6bf54a102
Revises: b7e31c2a9d1f
Create Date: 2026-04-25 21:16:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c2b6bf54a102"
down_revision = "b7e31c2a9d1f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("notification_type", sa.String(length=48), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_notifications_ticket_id", "hr_notifications", ["ticket_id"], unique=False)
    op.create_index("ix_hr_notifications_actor_id", "hr_notifications", ["actor_id"], unique=False)
    op.create_index("ix_hr_notifications_notification_type", "hr_notifications", ["notification_type"], unique=False)
    op.create_index("ix_hr_notifications_severity", "hr_notifications", ["severity"], unique=False)
    op.create_index("ix_hr_notifications_is_read", "hr_notifications", ["is_read"], unique=False)
    op.create_index("ix_hr_notifications_created_at", "hr_notifications", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_hr_notifications_created_at", table_name="hr_notifications")
    op.drop_index("ix_hr_notifications_is_read", table_name="hr_notifications")
    op.drop_index("ix_hr_notifications_severity", table_name="hr_notifications")
    op.drop_index("ix_hr_notifications_notification_type", table_name="hr_notifications")
    op.drop_index("ix_hr_notifications_actor_id", table_name="hr_notifications")
    op.drop_index("ix_hr_notifications_ticket_id", table_name="hr_notifications")
    op.drop_table("hr_notifications")
