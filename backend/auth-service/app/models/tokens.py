"""Одноразовые и долгоживущие секреты: коды подтверждения, refresh-токены,
состояние OAuth-входа. В БД хранятся только хэши."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import UserRole, user_role_enum


class EmailVerificationCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "email_verification_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthState(TimestampMixin, Base):
    """Состояние начатого входа через внешнего провайдера (state + PKCE)."""

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    code_verifier: Mapped[str] = mapped_column(String(128))
    nonce: Mapped[str] = mapped_column(String(64))
    # Роль, выбранная пользователем до входа: нужна при создании аккаунта.
    role: Mapped[UserRole | None] = mapped_column(user_role_enum)
    # Заполнен, если вошедший пользователь привязывает внешний аккаунт.
    link_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OAuthLoginCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Одноразовый код, который фронтенд обменивает на пару токенов
    после возврата от внешнего провайдера (токены не попадают в URL)."""

    __tablename__ = "oauth_login_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
