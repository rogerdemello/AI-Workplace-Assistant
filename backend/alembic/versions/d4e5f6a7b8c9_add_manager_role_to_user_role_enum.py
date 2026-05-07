"""Add manager role to user_role enum

Revision ID: d4e5f6a7b8c9
Revises: c8d4e2a1b3f0
Create Date: 2026-05-07
"""

from alembic import op


revision = "d4e5f6a7b8c9"
down_revision = "c8d4e2a1b3f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL only: add 'manager' to user_role enum if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'manager'
                AND enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'user_role'
                )
            ) THEN
                ALTER TYPE user_role ADD VALUE 'manager';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # To downgrade, create a new enum without 'manager', migrate data, drop old enum.
    # This is a no-op for safety; manual intervention required if truly needed.
    pass
