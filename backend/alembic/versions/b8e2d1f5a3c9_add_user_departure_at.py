"""Add departure_at to users for exit-survey triggers

Revision ID: b8e2d1f5a3c9
Revises: a7f1c0d4e2b8
Create Date: 2026-05-25 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8e2d1f5a3c9"
down_revision = "a7f1c0d4e2b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("departure_at", sa.DateTime(), nullable=True))
    op.create_index("ix_users_departure_at", "users", ["departure_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_departure_at", table_name="users")
    op.drop_column("users", "departure_at")
