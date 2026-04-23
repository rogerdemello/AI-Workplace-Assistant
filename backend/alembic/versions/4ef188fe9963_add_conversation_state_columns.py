"""Add conversation state columns

Revision ID: 4ef188fe9963
Revises: fcf688914963
Create Date: 2026-04-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '4ef188fe9963'
down_revision = 'fcf688914963'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('conversations', sa.Column('state', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('conversations', sa.Column('last_question', sa.String(length=255), nullable=True))
    op.add_column('conversations', sa.Column('completed', sa.Boolean(), server_default=sa.text('false'), nullable=True))


def downgrade() -> None:
    op.drop_column('conversations', 'completed')
    op.drop_column('conversations', 'last_question')
    op.drop_column('conversations', 'state')
