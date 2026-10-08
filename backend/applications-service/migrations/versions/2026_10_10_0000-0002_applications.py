"""Applications (responses to vacancies)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('applications',
    sa.Column('vacancy_id', sa.Uuid(), nullable=False),
    sa.Column('employer_id', sa.Uuid(), nullable=False),
    sa.Column('candidate_id', sa.Uuid(), nullable=False),
    sa.Column('vacancy_title', sa.String(length=200), nullable=False),
    sa.Column('company_name', sa.String(length=200), nullable=False),
    sa.Column('salary_from', sa.Integer(), nullable=True),
    sa.Column('salary_to', sa.Integer(), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('cover_letter', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('employer_message', sa.Text(), nullable=True),
    sa.Column('status_changed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_applications'))
    )
    op.create_index(op.f('ix_applications_candidate_id'), 'applications', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_applications_employer_id'), 'applications', ['employer_id'], unique=False)
    op.create_index(op.f('ix_applications_vacancy_id'), 'applications', ['vacancy_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_applications_vacancy_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_employer_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_candidate_id'), table_name='applications')
    op.drop_table('applications')
