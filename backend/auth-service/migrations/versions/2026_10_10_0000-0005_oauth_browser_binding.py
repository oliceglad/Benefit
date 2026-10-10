"""Bind OAuth state and login codes to the browser

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-10 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('oauth_states', sa.Column('browser_hash', sa.String(length=64), nullable=True))
    op.add_column('oauth_login_codes', sa.Column('browser_hash', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('oauth_login_codes', 'browser_hash')
    op.drop_column('oauth_states', 'browser_hash')
