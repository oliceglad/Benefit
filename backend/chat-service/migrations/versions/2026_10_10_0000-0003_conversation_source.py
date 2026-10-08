"""Conversation source: invitation or application

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
    op.add_column('conversations', sa.Column('source', sa.String(length=16), server_default='invitation', nullable=False))


def downgrade() -> None:
    op.drop_column('conversations', 'source')
