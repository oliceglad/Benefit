"""Candidate activities for profile actuality

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('candidate_activities',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('ref_id', sa.String(length=64), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['candidate_profiles.user_id'], name=op.f('fk_candidate_activities_user_id_candidate_profiles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_candidate_activities')),
    sa.UniqueConstraint('user_id', 'kind', 'ref_id', name=op.f('uq_candidate_activities_user_id'))
    )
    op.create_index(op.f('ix_candidate_activities_user_id'), 'candidate_activities', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_candidate_activities_user_id'), table_name='candidate_activities')
    op.drop_table('candidate_activities')
