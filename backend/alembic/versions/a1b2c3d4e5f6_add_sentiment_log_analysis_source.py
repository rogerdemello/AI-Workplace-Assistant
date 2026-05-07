"""Add analysis_source to sentiment_logs for LLM/lexicon/hybrid drift tracking.

Revision ID: a1b2c3d4e5f6
Revises: f36ac8f02d11
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f36ac8f02d11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sentiment_logs",
        sa.Column("analysis_source", sa.String(length=16), nullable=True),
    )
    op.create_index(
        "ix_sentiment_logs_analysis_source",
        "sentiment_logs",
        ["analysis_source"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sentiment_logs_analysis_source", table_name="sentiment_logs")
    op.drop_column("sentiment_logs", "analysis_source")
