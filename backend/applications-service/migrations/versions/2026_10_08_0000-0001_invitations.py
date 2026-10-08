"""Invitations and notification outbox

Revision ID: 0001
Revises:
Create Date: 2026-10-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('invitations',
    sa.Column('employer_id', sa.Uuid(), nullable=False),
    sa.Column('candidate_id', sa.Uuid(), nullable=False),
    sa.Column('vacancy_id', sa.String(length=64), nullable=True),
    sa.Column('vacancy_title', sa.String(length=200), nullable=False),
    sa.Column('company_name', sa.String(length=200), nullable=False),
    sa.Column('salary_from', sa.Integer(), nullable=True),
    sa.Column('salary_to', sa.Integer(), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('work_format', sa.String(length=16), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('response_message', sa.Text(), nullable=True),
    sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invitations'))
    )
    op.create_index(op.f('ix_invitations_candidate_id'), 'invitations', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_invitations_employer_id'), 'invitations', ['employer_id'], unique=False)
    op.create_table('outbox_messages',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('kind', sa.String(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_messages'))
    )


def downgrade() -> None:
    op.drop_table('outbox_messages')
    op.drop_index(op.f('ix_invitations_employer_id'), table_name='invitations')
    op.drop_index(op.f('ix_invitations_candidate_id'), table_name='invitations')
    op.drop_table('invitations')
