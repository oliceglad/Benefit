"""Company verification by open registries

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('verification_status', sa.String(length=24), server_default='unverified', nullable=False))
    op.add_column('companies', sa.Column('verification_checks', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('companies', sa.Column('registry_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('companies', sa.Column('verified_by', sa.String(length=16), nullable=True))
    op.add_column('companies', sa.Column('verification_note', sa.Text(), nullable=True))
    op.add_column('companies', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('companies', sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_companies_inn'), 'companies', ['inn'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_companies_inn'), table_name='companies')
    for column in ('checked_at', 'verified_at', 'verification_note', 'verified_by', 'registry_data', 'verification_checks', 'verification_status'):
        op.drop_column('companies', column)
