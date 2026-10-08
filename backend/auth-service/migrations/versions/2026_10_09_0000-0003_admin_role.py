"""Admin role

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09 00:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'admin'")


def downgrade() -> None:
    # PostgreSQL не умеет удалять значения enum; администраторов
    # переводим в работодателей, само значение остаётся неиспользуемым.
    op.execute("UPDATE users SET role = 'employer' WHERE role = 'admin'")
