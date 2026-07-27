"""Add is_anonymous to tickets

The Ticket model has carried ``is_anonymous`` (anonymous complaint flag) but no
migration ever added it — the column only appeared in environments built via
``create_all``. On Postgres deployments the column is absent, so any ORM query
that selects Ticket (e.g. GET /users/{id}/timeline) 500s with UndefinedColumn.
This backfills the column to match models/ticket.py.

Revision ID: e1f2a3b4c5d6
Revises: c9d3e7a1f4b2
Create Date: 2026-05-27 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "c9d3e7a1f4b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("tickets", "is_anonymous")
