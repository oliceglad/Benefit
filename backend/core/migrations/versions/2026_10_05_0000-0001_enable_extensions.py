"""Enable PostgreSQL extensions: pg_trgm, vector

Revision ID: 0001
Revises:
Create Date: 2026-10-05 00:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Нечёткий поиск по подстрокам и опечаткам (имена, навыки, должности).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # Векторные эмбеддинги для семантического сопоставления резюме и вакансий.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
