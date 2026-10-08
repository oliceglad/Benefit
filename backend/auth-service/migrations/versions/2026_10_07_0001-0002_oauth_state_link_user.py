"""OAuth state: link_user_id for linking external accounts

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("oauth_states", sa.Column("link_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_oauth_states_link_user_id_users",
        "oauth_states",
        "users",
        ["link_user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_oauth_states_link_user_id_users", "oauth_states", type_="foreignkey")
    op.drop_column("oauth_states", "link_user_id")
