"""Пользователь и его роль (RBAC)."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from sqlalchemy import DateTime, Enum, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(StrEnum):
    """Роли платформы. Значения совпадают с realm-ролями в Keycloak."""

    CANDIDATE = "candidate"
    EMPLOYER = "employer"
    # Администратор контента (тесты и т. п.). Не выбирается при регистрации,
    # выдаётся только командой ``python -m app.cli create-admin``.
    ADMIN = "admin"


# Роли, которые пользователь может выбрать сам.
SELF_SERVICE_ROLES = (UserRole.CANDIDATE, UserRole.EMPLOYER)
SelfServiceRole = Literal[UserRole.CANDIDATE, UserRole.EMPLOYER]


# Общий тип PostgreSQL для колонок с ролью.
user_role_enum = Enum(
    UserRole,
    name="user_role",
    values_callable=lambda roles: [role.value for role in roles],
)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Хранится в нижнем регистре.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    # NULL — аккаунт создан через внешнего провайдера и не имеет пароля.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(user_role_enum)
    full_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Защита от подбора пароля к конкретному аккаунту.
    failed_login_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    identities: Mapped[list["ExternalIdentity"]] = relationship(  # noqa: F821
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None
