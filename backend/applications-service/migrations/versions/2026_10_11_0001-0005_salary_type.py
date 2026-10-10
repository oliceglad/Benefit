"""Salary tax mode in invitation and application snapshots

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ('invitations', 'applications')


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column('salary_type', sa.String(length=8), server_default='gross', nullable=False))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, 'salary_type')
