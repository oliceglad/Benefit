"""Candidate search index and consumer offsets

Revision ID: 0001
Revises:
Create Date: 2026-10-10 00:00:00
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
    op.create_table('candidate_index',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('full_name', sa.String(length=300), nullable=False),
    sa.Column('headline', sa.String(length=200), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('relocation_ready', sa.Boolean(), nullable=False),
    sa.Column('job_search_status', sa.String(length=16), nullable=False),
    sa.Column('roles', postgresql.ARRAY(sa.String(length=32)), nullable=False),
    sa.Column('specialization', sa.String(length=32), nullable=True),
    sa.Column('grade', sa.String(length=16), nullable=True),
    sa.Column('grade_status', sa.String(length=16), nullable=False),
    sa.Column('verified_percent', sa.Double(), nullable=True),
    sa.Column('test_title', sa.String(length=200), nullable=True),
    sa.Column('industry', sa.String(length=32), nullable=True),
    sa.Column('skills', postgresql.ARRAY(sa.String(length=64)), nullable=False),
    sa.Column('skills_display', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('experience_months', sa.Integer(), nullable=False),
    sa.Column('work_formats', postgresql.ARRAY(sa.String(length=16)), nullable=False),
    sa.Column('employment_types', postgresql.ARRAY(sa.String(length=16)), nullable=False),
    sa.Column('salary_from', sa.Integer(), nullable=True),
    sa.Column('salary_currency', sa.String(length=3), nullable=True),
    sa.Column('fsp_count', sa.Integer(), nullable=False),
    sa.Column('fsp_achievements', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('activity', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('has_photo', sa.Boolean(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('about', sa.Text(), nullable=True),
    sa.Column('search_vector', postgresql.TSVECTOR(), nullable=False),
    sa.Column('indexed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_candidate_index'))
    )
    op.create_index('ix_candidate_index_roles', 'candidate_index', ['roles'], unique=False, postgresql_using='gin')
    op.create_index('ix_candidate_index_search', 'candidate_index', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index('ix_candidate_index_skills', 'candidate_index', ['skills'], unique=False, postgresql_using='gin')
    op.create_table('consumer_offsets',
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('last_event_id', sa.BigInteger(), nullable=False),
    sa.PrimaryKeyConstraint('name', name=op.f('pk_consumer_offsets'))
    )


def downgrade() -> None:
    op.drop_table('consumer_offsets')
    op.drop_index('ix_candidate_index_skills', table_name='candidate_index', postgresql_using='gin')
    op.drop_index('ix_candidate_index_search', table_name='candidate_index', postgresql_using='gin')
    op.drop_index('ix_candidate_index_roles', table_name='candidate_index', postgresql_using='gin')
    op.drop_table('candidate_index')
