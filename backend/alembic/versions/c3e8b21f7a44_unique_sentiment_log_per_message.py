"""One sentiment log per message, so reprocessing is safe

Revision ID: c3e8b21f7a44
Revises: b7d2f4a91c63
Create Date: 2026-07-28 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c3e8b21f7a44"
down_revision = "b7d2f4a91c63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Partial unique index: message_id is nullable (survey- and feedback-sourced
    # rows have no chat message), and Postgres treats NULLs as distinct anyway,
    # but stating the predicate keeps the intent obvious.
    #
    # Without this, reprocessing a message — a replay, a reconcile run, a retried
    # request — silently inserts a second row and skews that employee's score.
    # Verified against production before adding: 67 rows, 0 duplicates, 0 nulls.
    op.create_index(
        "uq_sentiment_logs_message_id",
        "sentiment_logs",
        ["message_id"],
        unique=True,
        postgresql_where=sa.text("message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_sentiment_logs_message_id", table_name="sentiment_logs")
