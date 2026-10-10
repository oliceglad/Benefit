"""Account lifecycle: code purposes, email change, deletion outbox

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-10 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('email_verification_codes', sa.Column('purpose', sa.String(length=16), server_default='verify_email', nullable=False))
    op.add_column('email_verification_codes', sa.Column('new_email', sa.String(length=320), nullable=True))
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


def downgrade() -> None:
    op.drop_table('outbox_messages')
    op.drop_column('email_verification_codes', 'new_email')
    op.drop_column('email_verification_codes', 'purpose')
