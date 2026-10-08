"""Contact grants: source (invitation or application) instead of invitation_id

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-10 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Переименование, а не пересоздание: выданные доступы сохраняются.
    op.alter_column("contact_grants", "invitation_id", new_column_name="source_id")
    op.add_column(
        "contact_grants",
        sa.Column("source", sa.String(16), server_default="invitation", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("contact_grants", "source")
    op.alter_column("contact_grants", "source_id", new_column_name="invitation_id")
