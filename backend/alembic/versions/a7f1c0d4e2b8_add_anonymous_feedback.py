"""Add anonymous_feedback table

Revision ID: a7f1c0d4e2b8
Revises: d4e5f6a7b8c9
Create Date: 2026-05-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7f1c0d4e2b8"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anonymous_feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="submitted"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anonymous_feedback_token_hash", "anonymous_feedback", ["token_hash"], unique=True)
    op.create_index("ix_anonymous_feedback_category", "anonymous_feedback", ["category"], unique=False)
    op.create_index("ix_anonymous_feedback_status", "anonymous_feedback", ["status"], unique=False)
    op.create_index("ix_anonymous_feedback_created_at", "anonymous_feedback", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_anonymous_feedback_created_at", table_name="anonymous_feedback")
    op.drop_index("ix_anonymous_feedback_status", table_name="anonymous_feedback")
    op.drop_index("ix_anonymous_feedback_category", table_name="anonymous_feedback")
    op.drop_index("ix_anonymous_feedback_token_hash", table_name="anonymous_feedback")
    op.drop_table("anonymous_feedback")
