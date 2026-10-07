"""Auth schema: users, external identities, verification codes, tokens

Revision ID: 0001
Revises:
Create Date: 2026-10-07 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM("candidate", "employer", name="user_role", create_type=False)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _user_fk(table: str) -> sa.Column:
    return sa.Column(
        "user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", name=f"fk_{table}_user_id_users", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("role", user_role, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "external_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        _user_fk("external_identities"),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_external_identities"),
        sa.UniqueConstraint("provider", "subject", name="uq_external_identities_provider"),
    )
    op.create_index("ix_external_identities_user_id", "external_identities", ["user_id"])

    op.create_table(
        "email_verification_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        _user_fk("email_verification_codes"),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_email_verification_codes"),
    )
    op.create_index("ix_email_verification_codes_user_id", "email_verification_codes", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        _user_fk("refresh_tokens"),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "oauth_states",
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("role", user_role, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("state", name="pk_oauth_states"),
    )

    op.create_table(
        "oauth_login_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        _user_fk("oauth_login_codes"),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_oauth_login_codes"),
        sa.UniqueConstraint("code_hash", name="uq_oauth_login_codes_code_hash"),
    )
    op.create_index("ix_oauth_login_codes_user_id", "oauth_login_codes", ["user_id"])


def downgrade() -> None:
    op.drop_table("oauth_login_codes")
    op.drop_table("oauth_states")
    op.drop_table("refresh_tokens")
    op.drop_table("email_verification_codes")
    op.drop_table("external_identities")
    op.drop_table("users")
    user_role.drop(op.get_bind(), checkfirst=True)
