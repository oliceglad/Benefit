"""Assessments, tasks, attempts, outbox

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
    op.create_table('assessments',
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('specialization', sa.String(length=32), nullable=False),
    sa.Column('grade', sa.String(length=16), nullable=False),
    sa.Column('time_limit_seconds', sa.Integer(), nullable=False),
    sa.Column('tasks_per_attempt', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_assessments')),
    sa.UniqueConstraint('slug', name=op.f('uq_assessments_slug'))
    )
    op.create_index(op.f('ix_assessments_specialization'), 'assessments', ['specialization'], unique=False)
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
    op.create_table('assessment_tasks',
    sa.Column('assessment_id', sa.Uuid(), nullable=False),
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('prompt', sa.Text(), nullable=False),
    sa.Column('code', sa.Text(), nullable=True),
    sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('correct', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('points', sa.Integer(), nullable=False),
    sa.Column('time_limit_seconds', sa.Integer(), nullable=False),
    sa.Column('skills', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], name=op.f('fk_assessment_tasks_assessment_id_assessments'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_assessment_tasks')),
    sa.UniqueConstraint('assessment_id', 'key', name=op.f('uq_assessment_tasks_assessment_id'))
    )
    op.create_index(op.f('ix_assessment_tasks_assessment_id'), 'assessment_tasks', ['assessment_id'], unique=False)
    op.create_table('attempts',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('assessment_id', sa.Uuid(), nullable=False),
    sa.Column('specialization', sa.String(length=32), nullable=False),
    sa.Column('target_grade', sa.String(length=16), nullable=False),
    sa.Column('claimed_grade', sa.String(length=16), nullable=True),
    sa.Column('survey', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deadline_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('duration_seconds', sa.Double(), nullable=True),
    sa.Column('score', sa.Double(), nullable=True),
    sa.Column('max_score', sa.Integer(), nullable=False),
    sa.Column('percent', sa.Double(), nullable=True),
    sa.Column('outcome', sa.String(length=16), nullable=True),
    sa.Column('confirmed_grade', sa.String(length=16), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], name=op.f('fk_attempts_assessment_id_assessments')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_attempts'))
    )
    op.create_index(op.f('ix_attempts_assessment_id'), 'attempts', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_attempts_user_id'), 'attempts', ['user_id'], unique=False)
    op.create_table('attempt_tasks',
    sa.Column('attempt_id', sa.Uuid(), nullable=False),
    sa.Column('task_id', sa.Uuid(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('max_points', sa.Integer(), nullable=False),
    sa.Column('time_limit_seconds', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('time_spent_seconds', sa.Double(), nullable=True),
    sa.Column('answer', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('is_correct', sa.Boolean(), nullable=True),
    sa.Column('points_awarded', sa.Double(), server_default='0', nullable=False),
    sa.Column('timed_out', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('skipped', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['attempt_id'], ['attempts.id'], name=op.f('fk_attempt_tasks_attempt_id_attempts'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['task_id'], ['assessment_tasks.id'], name=op.f('fk_attempt_tasks_task_id_assessment_tasks')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_attempt_tasks'))
    )
    op.create_index(op.f('ix_attempt_tasks_attempt_id'), 'attempt_tasks', ['attempt_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_attempt_tasks_attempt_id'), table_name='attempt_tasks')
    op.drop_table('attempt_tasks')
    op.drop_index(op.f('ix_attempts_user_id'), table_name='attempts')
    op.drop_index(op.f('ix_attempts_assessment_id'), table_name='attempts')
    op.drop_table('attempts')
    op.drop_index(op.f('ix_assessment_tasks_assessment_id'), table_name='assessment_tasks')
    op.drop_table('assessment_tasks')
    op.drop_table('outbox_messages')
    op.drop_index(op.f('ix_assessments_specialization'), table_name='assessments')
    op.drop_table('assessments')
