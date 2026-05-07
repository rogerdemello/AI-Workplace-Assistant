"""add message signals

Revision ID: f36ac8f02d11
Revises: e91a3c7f4b12
Create Date: 2026-04-29 09:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f36ac8f02d11"
down_revision = "e91a3c7f4b12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "message_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("emotion", sa.String(length=50), nullable=False, server_default="neutral"),
        sa.Column("topic", sa.String(length=80), nullable=False, server_default="general"),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="low"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_message_signals_employee_id", "message_signals", ["employee_id"], unique=False)
    op.create_index("ix_message_signals_message_id", "message_signals", ["message_id"], unique=False)
    op.create_index("ix_message_signals_emotion", "message_signals", ["emotion"], unique=False)
    op.create_index("ix_message_signals_topic", "message_signals", ["topic"], unique=False)
    op.create_index("ix_message_signals_severity", "message_signals", ["severity"], unique=False)
    op.create_index("ix_message_signals_created_at", "message_signals", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_message_signals_created_at", table_name="message_signals")
    op.drop_index("ix_message_signals_severity", table_name="message_signals")
    op.drop_index("ix_message_signals_topic", table_name="message_signals")
    op.drop_index("ix_message_signals_emotion", table_name="message_signals")
    op.drop_index("ix_message_signals_message_id", table_name="message_signals")
    op.drop_index("ix_message_signals_employee_id", table_name="message_signals")
    op.drop_table("message_signals")
