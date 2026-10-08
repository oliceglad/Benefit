"""Candidate profiles, photos, FSP achievements, consents, outbox events

Revision ID: 0001
Revises:
Create Date: 2026-10-07 00:00:00
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
    op.create_table('candidate_profiles',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='draft', nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_name', sa.String(length=100), nullable=True),
    sa.Column('first_name', sa.String(length=100), nullable=True),
    sa.Column('middle_name', sa.String(length=100), nullable=True),
    sa.Column('birth_date', sa.Date(), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('relocation_ready', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('contact_email', sa.String(length=320), nullable=True),
    sa.Column('telegram', sa.String(length=64), nullable=True),
    sa.Column('links', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('headline', sa.String(length=200), nullable=True),
    sa.Column('about', sa.Text(), nullable=True),
    sa.Column('grade', sa.String(length=16), nullable=True),
    sa.Column('verified_grade', sa.String(length=16), nullable=True),
    sa.Column('grade_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('roles', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('skills', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('soft_skills', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('languages', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('experience', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('education', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('courses', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('projects', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('salary_from', sa.Integer(), nullable=True),
    sa.Column('salary_currency', sa.String(length=3), server_default='RUB', nullable=False),
    sa.Column('employment_types', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('work_formats', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('job_search_status', sa.String(length=16), server_default='active', nullable=False),
    sa.Column('privacy', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
    sa.Column('fsp_participant_id', sa.String(length=64), nullable=True),
    sa.Column('fsp_synced_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_candidate_profiles'))
    )
    op.create_table('consents',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=32), nullable=False),
    sa.Column('version', sa.String(length=32), nullable=False),
    sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_consents'))
    )
    op.create_index(op.f('ix_consents_user_id'), 'consents', ['user_id'], unique=False)
    op.create_table('outbox_events',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('aggregate_id', sa.Uuid(), nullable=False),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_events'))
    )
    op.create_index(op.f('ix_outbox_events_aggregate_id'), 'outbox_events', ['aggregate_id'], unique=False)
    op.create_table('candidate_photos',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('content', sa.LargeBinary(), nullable=False),
    sa.Column('content_type', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['candidate_profiles.user_id'], name=op.f('fk_candidate_photos_user_id_candidate_profiles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_candidate_photos'))
    )
    op.create_table('fsp_achievements',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('external_id', sa.String(length=64), nullable=False),
    sa.Column('event', sa.String(length=300), nullable=False),
    sa.Column('discipline', sa.String(length=200), nullable=True),
    sa.Column('level', sa.String(length=32), nullable=True),
    sa.Column('result', sa.String(length=32), nullable=True),
    sa.Column('place', sa.Integer(), nullable=True),
    sa.Column('team', sa.String(length=200), nullable=True),
    sa.Column('event_date', sa.Date(), nullable=True),
    sa.Column('url', sa.String(length=500), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['candidate_profiles.user_id'], name=op.f('fk_fsp_achievements_user_id_candidate_profiles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_fsp_achievements')),
    sa.UniqueConstraint('user_id', 'external_id', name=op.f('uq_fsp_achievements_user_id'))
    )
    op.create_index(op.f('ix_fsp_achievements_user_id'), 'fsp_achievements', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fsp_achievements_user_id'), table_name='fsp_achievements')
    op.drop_table('fsp_achievements')
    op.drop_table('candidate_photos')
    op.drop_index(op.f('ix_outbox_events_aggregate_id'), table_name='outbox_events')
    op.drop_table('outbox_events')
    op.drop_index(op.f('ix_consents_user_id'), table_name='consents')
    op.drop_table('consents')
    op.drop_table('candidate_profiles')
