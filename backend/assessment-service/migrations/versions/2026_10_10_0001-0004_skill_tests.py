"""Skill tests: assessment kind, skill and level scale; skill attempts

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-10 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assessments",
        sa.Column("kind", sa.String(16), server_default="grade", nullable=False),
    )
    op.add_column("assessments", sa.Column("skill", sa.String(64), nullable=True))
    op.add_column(
        "assessments",
        sa.Column(
            "levels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_assessments_skill"), "assessments", ["skill"])
    op.alter_column("assessments", "specialization", nullable=True)
    op.alter_column("assessments", "grade", nullable=True)

    op.add_column("attempts", sa.Column("skill", sa.String(64), nullable=True))
    op.add_column(
        "attempts", sa.Column("confirmed_level", sa.String(16), nullable=True)
    )
    op.alter_column("attempts", "specialization", nullable=True)
    op.alter_column("attempts", "target_grade", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM attempts WHERE skill IS NOT NULL")
    op.execute("DELETE FROM assessments WHERE kind = 'skill'")
    op.alter_column("attempts", "target_grade", nullable=False)
    op.alter_column("attempts", "specialization", nullable=False)
    op.drop_column("attempts", "confirmed_level")
    op.drop_column("attempts", "skill")
    op.alter_column("assessments", "grade", nullable=False)
    op.alter_column("assessments", "specialization", nullable=False)
    op.drop_index(op.f("ix_assessments_skill"), table_name="assessments")
    op.drop_column("assessments", "levels")
    op.drop_column("assessments", "skill")
    op.drop_column("assessments", "kind")
