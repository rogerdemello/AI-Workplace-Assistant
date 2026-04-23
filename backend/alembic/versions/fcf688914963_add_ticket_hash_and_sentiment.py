"""Add ticket hash and sentiment

Revision ID: fcf688914963
Revises: 
Create Date: 2026-04-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fcf688914963'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tickets', sa.Column('hash', sa.String(length=64), nullable=True))
    op.add_column('tickets', sa.Column('sentiment_score', sa.Integer(), nullable=True))
    op.create_index('ix_tickets_hash', 'tickets', ['hash'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_tickets_hash', table_name='tickets')
    op.drop_column('tickets', 'sentiment_score')
    op.drop_column('tickets', 'hash')
