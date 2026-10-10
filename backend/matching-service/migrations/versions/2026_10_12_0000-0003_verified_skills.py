"""Skill levels verified by platform tests in candidate index

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-12 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_index",
        sa.Column(
            "verified_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    # Перестроить индекс по ленте событий с начала (идемпотентно).
    op.execute("UPDATE consumer_offsets SET last_event_id = 0")


def downgrade() -> None:
    op.drop_column("candidate_index", "verified_skills")
