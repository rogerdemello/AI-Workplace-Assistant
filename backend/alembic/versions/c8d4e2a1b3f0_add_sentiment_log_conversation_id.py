"""add conversation_id to sentiment_logs

Revision ID: c8d4e2a1b3f0
Revises: a1b2c3d4e5f6
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c8d4e2a1b3f0"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sentiment_logs",
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_sentiment_logs_conversation_id",
        "sentiment_logs",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sentiment_logs_conversation_id", table_name="sentiment_logs")
    op.drop_column("sentiment_logs", "conversation_id")
