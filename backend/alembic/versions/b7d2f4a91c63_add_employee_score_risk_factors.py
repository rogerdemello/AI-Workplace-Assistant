"""Add employee_scores.risk_factors so a risk score can be explained

Revision ID: b7d2f4a91c63
Revises: a4c8e17b2d59
Create Date: 2026-07-28 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "b7d2f4a91c63"
down_revision = "a4c8e17b2d59"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable with no backfill: existing rows get their factors on the next
    # recompute, which happens on the employee's next message. A backfill would
    # have to invent inputs it cannot reconstruct.
    op.add_column(
        "employee_scores",
        sa.Column("risk_factors", JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("employee_scores", "risk_factors")
