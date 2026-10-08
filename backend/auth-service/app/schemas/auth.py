"""Схемы запросов и ответов аутентификации."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.config import settings
from app.models.user import UserRole


def _normalize_email(value: str) -> str:
    return value.strip().lower()


class EmailRequest(BaseModel):
    email: EmailStr

    _normalize = field_validator("email", mode="after")(_normalize_email)


class RegisterRequest(EmailRequest):
    password: str = Field(min_length=settings.password_min_length, max_length=128)
    role: UserRole
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def _check_password_strength(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value) or not any(
            ch.isdigit() for ch in value
        ):
            raise ValueError("Пароль должен содержать буквы и цифры")
        return value


class RegisterResponse(BaseModel):
    email: EmailStr
    code_expires_in: int = Field(description="Срок действия кода, секунды")
    resend_available_in: int = Field(
        description="Через сколько секунд можно запросить код повторно"
    )


class VerifyEmailRequest(EmailRequest):
    code: str = Field(pattern=r"^\d{6}$")


class LoginRequest(EmailRequest):
    password: str = Field(max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(max_length=256)


class OAuthExchangeRequest(BaseModel):
    code: str = Field(max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    refresh_expires_in: int


class AuthorizationUrlResponse(BaseModel):
    authorization_url: str


class ProviderInfo(BaseModel):
    id: str
    name: str
