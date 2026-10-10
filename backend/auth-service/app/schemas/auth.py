"""Схемы запросов и ответов аутентификации."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field, field_validator

from app.core.config import settings
from app.models.user import SelfServiceRole


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _check_password_strength(value: str) -> str:
    if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
        raise ValueError("Пароль должен содержать буквы и цифры")
    return value


# Новый пароль: те же правила, что и при регистрации.
NewPassword = Annotated[
    str,
    Field(min_length=settings.password_min_length, max_length=128),
    AfterValidator(_check_password_strength),
]
Code = Annotated[str, Field(pattern=r"^\d{6}$")]


class EmailRequest(BaseModel):
    email: EmailStr

    _normalize = field_validator("email", mode="after")(_normalize_email)


class RegisterRequest(EmailRequest):
    password: NewPassword
    role: SelfServiceRole
    full_name: str | None = Field(default=None, max_length=255)


class RegisterResponse(BaseModel):
    email: EmailStr
    code_expires_in: int = Field(description="Срок действия кода, секунды")
    resend_available_in: int = Field(
        description="Через сколько секунд можно запросить код повторно"
    )


class VerifyEmailRequest(EmailRequest):
    code: Code


class PasswordResetRequest(EmailRequest):
    """Сброс пароля по коду из письма."""

    code: Code
    new_password: NewPassword


class LoginRequest(EmailRequest):
    password: str = Field(max_length=128)


class RefreshRequest(BaseModel):
    # Не указан — берётся из cookie (режим cookie).
    refresh_token: str | None = Field(default=None, max_length=256)


class OAuthExchangeRequest(BaseModel):
    code: str = Field(max_length=256)


class TokenResponse(BaseModel):
    """В режиме cookie токены в теле не возвращаются (они в HttpOnly-cookie),
    вместо них — ``csrf_token`` для заголовка ``X-CSRF-Token``."""

    access_token: str | None
    refresh_token: str | None
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    refresh_expires_in: int
    delivery: Literal["body", "cookie"] = "body"
    csrf_token: str | None = None


class AuthorizationUrlResponse(BaseModel):
    authorization_url: str


class ProviderInfo(BaseModel):
    id: str
    name: str
