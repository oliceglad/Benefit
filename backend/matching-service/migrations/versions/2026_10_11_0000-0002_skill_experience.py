"""Skill experience evidence in candidate index

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_index",
        sa.Column(
            "skill_experience",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    # Перечитать ленту событий с начала: индексатор перестроит все записи
    # с новыми данными (идемпотентно).
    op.execute("UPDATE consumer_offsets SET last_event_id = 0")


def downgrade() -> None:
    op.drop_column("candidate_index", "skill_experience")
