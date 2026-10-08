"""Employer-owned tests and test assignments

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('test_assignments',
    sa.Column('assessment_id', sa.Uuid(), nullable=False),
    sa.Column('employer_id', sa.Uuid(), nullable=False),
    sa.Column('candidate_id', sa.Uuid(), nullable=False),
    sa.Column('conversation_id', sa.Uuid(), nullable=False),
    sa.Column('company_name', sa.String(length=200), nullable=False),
    sa.Column('vacancy_title', sa.String(length=200), nullable=False),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('due_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], name=op.f('fk_test_assignments_assessment_id_assessments')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_test_assignments'))
    )
    op.create_index(op.f('ix_test_assignments_assessment_id'), 'test_assignments', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_test_assignments_candidate_id'), 'test_assignments', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_test_assignments_employer_id'), 'test_assignments', ['employer_id'], unique=False)
    op.add_column('assessments', sa.Column('owner_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_assessments_owner_id'), 'assessments', ['owner_id'], unique=False)
    op.add_column('attempts', sa.Column('assignment_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_attempts_assignment_id'), 'attempts', ['assignment_id'], unique=False)
    op.create_foreign_key(op.f('fk_attempts_assignment_id_test_assignments'), 'attempts', 'test_assignments', ['assignment_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(op.f('fk_attempts_assignment_id_test_assignments'), 'attempts', type_='foreignkey')
    op.drop_index(op.f('ix_attempts_assignment_id'), table_name='attempts')
    op.drop_column('attempts', 'assignment_id')
    op.drop_index(op.f('ix_assessments_owner_id'), table_name='assessments')
    op.drop_column('assessments', 'owner_id')
    op.drop_index(op.f('ix_test_assignments_employer_id'), table_name='test_assignments')
    op.drop_index(op.f('ix_test_assignments_candidate_id'), table_name='test_assignments')
    op.drop_index(op.f('ix_test_assignments_assessment_id'), table_name='test_assignments')
    op.drop_table('test_assignments')
