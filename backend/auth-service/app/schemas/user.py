"""Схемы пользователя."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class IdentityResponse(BaseModel):
    """Привязанный внешний аккаунт (ФСП ID, Keycloak)."""

    model_config = ConfigDict(from_attributes=True)

    provider: str
    email: str | None
    created_at: datetime


class InternalIdentityResponse(IdentityResponse):
    """Для других сервисов: включает идентификатор во внешней системе."""

    subject: str


class InternalUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: UserRole
    full_name: str | None
    is_active: bool
    is_email_verified: bool


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: UserRole
    full_name: str | None
    is_email_verified: bool
    # Нет пароля — смена почты и удаление подтверждаются кодом из письма,
    # а пароль задаётся через восстановление.
    has_password: bool
    created_at: datetime
