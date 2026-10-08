"""Candidate category: industry, verified specialization, verification details

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('candidate_profiles', sa.Column('industry', sa.String(length=32), nullable=True))
    op.add_column('candidate_profiles', sa.Column('verified_specialization', sa.String(length=32), nullable=True))
    op.add_column('candidate_profiles', sa.Column('verification', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))


def downgrade() -> None:
    op.drop_column('candidate_profiles', 'verification')
    op.drop_column('candidate_profiles', 'verified_specialization')
    op.drop_column('candidate_profiles', 'industry')
