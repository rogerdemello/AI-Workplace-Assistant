"""Add automation rules table

Revision ID: d31fe3baf7ee
Revises: c2b6bf54a102
Create Date: 2026-04-26 12:22:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d31fe3baf7ee"
down_revision = "c2b6bf54a102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_rules_name", "automation_rules", ["name"], unique=False)
    op.create_index("ix_automation_rules_event_type", "automation_rules", ["event_type"], unique=False)
    op.create_index("ix_automation_rules_enabled", "automation_rules", ["enabled"], unique=False)
    op.create_index("ix_automation_rules_created_by", "automation_rules", ["created_by"], unique=False)
    op.create_index("ix_automation_rules_created_at", "automation_rules", ["created_at"], unique=False)
    op.create_index("ix_automation_rules_updated_at", "automation_rules", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_automation_rules_updated_at", table_name="automation_rules")
    op.drop_index("ix_automation_rules_created_at", table_name="automation_rules")
    op.drop_index("ix_automation_rules_created_by", table_name="automation_rules")
    op.drop_index("ix_automation_rules_enabled", table_name="automation_rules")
    op.drop_index("ix_automation_rules_event_type", table_name="automation_rules")
    op.drop_index("ix_automation_rules_name", table_name="automation_rules")
    op.drop_table("automation_rules")
