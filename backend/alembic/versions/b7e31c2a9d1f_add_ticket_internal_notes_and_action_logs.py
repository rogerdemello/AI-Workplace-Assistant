"""Add ticket internal notes and action logs

Revision ID: b7e31c2a9d1f
Revises: 4ef188fe9963
Create Date: 2026-04-25 20:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e31c2a9d1f'
down_revision = '4ef188fe9963'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ticket_messages', sa.Column('is_internal', sa.Integer(), server_default='0', nullable=False))
    op.create_index('ix_ticket_messages_is_internal', 'ticket_messages', ['is_internal'], unique=False)

    op.create_table(
        'ticket_action_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('actor_id', sa.UUID(), nullable=True),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ticket_action_logs_ticket_id', 'ticket_action_logs', ['ticket_id'], unique=False)
    op.create_index('ix_ticket_action_logs_actor_id', 'ticket_action_logs', ['actor_id'], unique=False)
    op.create_index('ix_ticket_action_logs_action_type', 'ticket_action_logs', ['action_type'], unique=False)
    op.create_index('ix_ticket_action_logs_created_at', 'ticket_action_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ticket_action_logs_created_at', table_name='ticket_action_logs')
    op.drop_index('ix_ticket_action_logs_action_type', table_name='ticket_action_logs')
    op.drop_index('ix_ticket_action_logs_actor_id', table_name='ticket_action_logs')
    op.drop_index('ix_ticket_action_logs_ticket_id', table_name='ticket_action_logs')
    op.drop_table('ticket_action_logs')

    op.drop_index('ix_ticket_messages_is_internal', table_name='ticket_messages')
    op.drop_column('ticket_messages', 'is_internal')
