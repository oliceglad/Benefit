"""Company links for verification badge

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ('invitations', 'applications', 'hiring_processes')


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column('company_id', sa.Uuid(), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, 'company_id')
