"""add sentiment logs and employee scores

Revision ID: e91a3c7f4b12
Revises: d31fe3baf7ee
Create Date: 2026-04-29 08:55:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "e91a3c7f4b12"
down_revision = "d31fe3baf7ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_scores",
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True, nullable=False),
        sa.Column("sentiment_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("engagement_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mental_health_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("trend_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trend_label", sa.String(length=20), nullable=False, server_default="stable"),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_employee_scores_employee_id", "employee_scores", ["employee_id"], unique=False)

    op.create_table(
        "sentiment_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=20), nullable=False),
        sa.Column("emotion", sa.String(length=50), nullable=False, server_default="neutral"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sentiment_logs_employee_id", "sentiment_logs", ["employee_id"], unique=False)
    op.create_index("ix_sentiment_logs_message_id", "sentiment_logs", ["message_id"], unique=False)
    op.create_index("ix_sentiment_logs_score", "sentiment_logs", ["score"], unique=False)
    op.create_index("ix_sentiment_logs_label", "sentiment_logs", ["label"], unique=False)
    op.create_index("ix_sentiment_logs_created_at", "sentiment_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sentiment_logs_created_at", table_name="sentiment_logs")
    op.drop_index("ix_sentiment_logs_label", table_name="sentiment_logs")
    op.drop_index("ix_sentiment_logs_score", table_name="sentiment_logs")
    op.drop_index("ix_sentiment_logs_message_id", table_name="sentiment_logs")
    op.drop_index("ix_sentiment_logs_employee_id", table_name="sentiment_logs")
    op.drop_table("sentiment_logs")

    op.drop_index("ix_employee_scores_employee_id", table_name="employee_scores")
    op.drop_table("employee_scores")
