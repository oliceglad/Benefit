"""Hiring need hard filters and candidate feedback

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('need_feedback',
    sa.Column('need_id', sa.Uuid(), nullable=False),
    sa.Column('candidate_id', sa.Uuid(), nullable=False),
    sa.Column('verdict', sa.String(length=16), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['need_id'], ['hiring_needs.id'], name=op.f('fk_need_feedback_need_id_hiring_needs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_need_feedback')),
    sa.UniqueConstraint('need_id', 'candidate_id', name=op.f('uq_need_feedback_need_id'))
    )
    op.create_index(op.f('ix_need_feedback_need_id'), 'need_feedback', ['need_id'], unique=False)
    op.add_column('hiring_needs', sa.Column('strict_skills', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('hiring_needs', sa.Column('grade_tolerance', sa.Integer(), server_default='1', nullable=False))
    op.add_column('hiring_needs', sa.Column('min_experience_months', sa.Integer(), nullable=True))
    op.add_column('hiring_needs', sa.Column('hard_budget', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('hiring_needs', sa.Column('strict_format', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('hiring_needs', 'strict_format')
    op.drop_column('hiring_needs', 'hard_budget')
    op.drop_column('hiring_needs', 'min_experience_months')
    op.drop_column('hiring_needs', 'grade_tolerance')
    op.drop_column('hiring_needs', 'strict_skills')
    op.drop_index(op.f('ix_need_feedback_need_id'), table_name='need_feedback')
    op.drop_table('need_feedback')
