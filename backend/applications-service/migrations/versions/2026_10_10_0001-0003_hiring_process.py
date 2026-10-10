"""Hiring process: stages, team, interviews, offers, history

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    ]


def upgrade() -> None:
    op.create_table('team_members',
    sa.Column('employer_id', sa.Uuid(), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('position', sa.String(length=200), nullable=True),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    *_timestamps(),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_team_members'))
    )
    op.create_index(op.f('ix_team_members_employer_id'), 'team_members', ['employer_id'], unique=False)

    op.create_table('hiring_processes',
    sa.Column('employer_id', sa.Uuid(), nullable=False),
    sa.Column('candidate_id', sa.Uuid(), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('source_id', sa.Uuid(), nullable=False),
    sa.Column('vacancy_id', sa.String(length=64), nullable=True),
    sa.Column('vacancy_title', sa.String(length=200), nullable=False),
    sa.Column('company_name', sa.String(length=200), nullable=False),
    sa.Column('stage', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('responsible_id', sa.Uuid(), nullable=True),
    sa.Column('rejection_reason', sa.Text(), nullable=True),
    sa.Column('stage_changed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    *_timestamps(),
    sa.ForeignKeyConstraint(['responsible_id'], ['team_members.id'], name=op.f('fk_hiring_processes_responsible_id_team_members'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_hiring_processes')),
    sa.UniqueConstraint('source', 'source_id', name=op.f('uq_hiring_processes_source'))
    )
    op.create_index(op.f('ix_hiring_processes_candidate_id'), 'hiring_processes', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_hiring_processes_employer_id'), 'hiring_processes', ['employer_id'], unique=False)
    op.create_index(op.f('ix_hiring_processes_vacancy_id'), 'hiring_processes', ['vacancy_id'], unique=False)

    op.create_table('interviews',
    sa.Column('process_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('duration_minutes', sa.SmallInteger(), nullable=False),
    sa.Column('format', sa.String(length=16), nullable=False),
    sa.Column('location', sa.String(length=500), nullable=True),
    sa.Column('interviewer_ids', postgresql.ARRAY(sa.Uuid()), nullable=False),
    sa.Column('note_for_candidate', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('rating', sa.SmallInteger(), nullable=True),
    sa.Column('feedback', sa.Text(), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    *_timestamps(),
    sa.ForeignKeyConstraint(['process_id'], ['hiring_processes.id'], name=op.f('fk_interviews_process_id_hiring_processes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_interviews'))
    )
    op.create_index(op.f('ix_interviews_process_id'), 'interviews', ['process_id'], unique=False)

    op.create_table('job_offers',
    sa.Column('process_id', sa.Uuid(), nullable=False),
    sa.Column('position_title', sa.String(length=200), nullable=False),
    sa.Column('salary', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('salary_type', sa.String(length=8), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('employment_type', sa.String(length=16), nullable=True),
    sa.Column('work_format', sa.String(length=16), nullable=True),
    sa.Column('benefits', sa.Text(), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('candidate_message', sa.Text(), nullable=True),
    sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    *_timestamps(),
    sa.ForeignKeyConstraint(['process_id'], ['hiring_processes.id'], name=op.f('fk_job_offers_process_id_hiring_processes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_job_offers'))
    )
    op.create_index(op.f('ix_job_offers_process_id'), 'job_offers', ['process_id'], unique=False)

    op.create_table('hiring_events',
    sa.Column('process_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=32), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('actor_role', sa.String(length=16), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('visible_to_candidate', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['process_id'], ['hiring_processes.id'], name=op.f('fk_hiring_events_process_id_hiring_processes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_hiring_events'))
    )
    op.create_index(op.f('ix_hiring_events_process_id'), 'hiring_events', ['process_id'], unique=False)

    # Процессы для уже существующих откликов и принятых приглашений.
    op.execute("""
        INSERT INTO hiring_processes (
            id, employer_id, candidate_id, source, source_id, vacancy_id,
            vacancy_title, company_name, stage, status, stage_changed_at,
            closed_at, created_at, updated_at
        )
        SELECT gen_random_uuid(), employer_id, candidate_id, 'application', id,
               vacancy_id::text, vacancy_title, company_name,
               CASE WHEN status = 'invited' THEN 'interview' ELSE 'new' END,
               CASE status
                   WHEN 'rejected' THEN 'rejected'
                   WHEN 'withdrawn' THEN 'withdrawn'
                   ELSE 'active'
               END,
               coalesce(status_changed_at, created_at),
               CASE WHEN status IN ('rejected', 'withdrawn')
                    THEN coalesce(status_changed_at, updated_at) END,
               created_at, updated_at
        FROM applications
    """)
    op.execute("""
        INSERT INTO hiring_processes (
            id, employer_id, candidate_id, source, source_id, vacancy_id,
            vacancy_title, company_name, stage, status, stage_changed_at,
            created_at, updated_at
        )
        SELECT gen_random_uuid(), employer_id, candidate_id, 'invitation', id,
               vacancy_id, vacancy_title, company_name, 'new', 'active',
               coalesce(responded_at, created_at),
               coalesce(responded_at, created_at), updated_at
        FROM invitations
        WHERE status = 'accepted'
    """)
    op.execute("""
        INSERT INTO hiring_events (
            id, process_id, type, actor_id, actor_role, data,
            visible_to_candidate, created_at
        )
        SELECT gen_random_uuid(), id, 'created', candidate_id, 'candidate',
               jsonb_build_object('source', source), true, created_at
        FROM hiring_processes
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_hiring_events_process_id'), table_name='hiring_events')
    op.drop_table('hiring_events')
    op.drop_index(op.f('ix_job_offers_process_id'), table_name='job_offers')
    op.drop_table('job_offers')
    op.drop_index(op.f('ix_interviews_process_id'), table_name='interviews')
    op.drop_table('interviews')
    op.drop_index(op.f('ix_hiring_processes_vacancy_id'), table_name='hiring_processes')
    op.drop_index(op.f('ix_hiring_processes_employer_id'), table_name='hiring_processes')
    op.drop_index(op.f('ix_hiring_processes_candidate_id'), table_name='hiring_processes')
    op.drop_table('hiring_processes')
    op.drop_index(op.f('ix_team_members_employer_id'), table_name='team_members')
    op.drop_table('team_members')
