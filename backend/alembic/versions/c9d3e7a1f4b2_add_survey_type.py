"""Add survey_type for lifecycle targeting

Revision ID: c9d3e7a1f4b2
Revises: b8e2d1f5a3c9
Create Date: 2026-05-25 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9d3e7a1f4b2"
down_revision = "b8e2d1f5a3c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("surveys", sa.Column("survey_type", sa.String(length=32), nullable=True))
    op.create_index("ix_surveys_survey_type", "surveys", ["survey_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_surveys_survey_type", table_name="surveys")
    op.drop_column("surveys", "survey_type")
