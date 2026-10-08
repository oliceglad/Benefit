"""Contact grants: employers whose invitation the candidate accepted

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('contact_grants',
    sa.Column('candidate_id', sa.Uuid(), nullable=False),
    sa.Column('employer_id', sa.Uuid(), nullable=False),
    sa.Column('invitation_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidate_profiles.user_id'], name=op.f('fk_contact_grants_candidate_id_candidate_profiles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_contact_grants')),
    sa.UniqueConstraint('candidate_id', 'employer_id', name=op.f('uq_contact_grants_candidate_id'))
    )
    op.create_index(op.f('ix_contact_grants_candidate_id'), 'contact_grants', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_contact_grants_employer_id'), 'contact_grants', ['employer_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_contact_grants_employer_id'), table_name='contact_grants')
    op.drop_index(op.f('ix_contact_grants_candidate_id'), table_name='contact_grants')
    op.drop_table('contact_grants')
