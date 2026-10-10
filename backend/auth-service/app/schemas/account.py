"""Схемы управления аккаунтом: пароль, почта, профиль, удаление."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.schemas.auth import Code, NewPassword, _normalize_email


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
        ]
        | None
    ) = None


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(max_length=128)
    new_password: NewPassword


class EmailChangeRequest(BaseModel):
    """Смена почты: код придёт на новый адрес."""

    model_config = ConfigDict(extra="forbid")

    new_email: EmailStr
    # Обязателен, если у аккаунта есть пароль.
    password: str | None = Field(default=None, max_length=128)

    def normalized_email(self) -> str:
        return _normalize_email(str(self.new_email))


class CodeConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Code


class AccountDelete(BaseModel):
    """Подтверждение удаления: пароль или код из письма
    (``POST /users/me/delete-code``) — для аккаунтов без пароля."""

    model_config = ConfigDict(extra="forbid")

    password: str | None = Field(default=None, max_length=128)
    code: Code | None = None


class CodeSent(BaseModel):
    """Код отправлен: через сколько он истечёт и когда можно запросить снова."""

    email: str
    code_expires_in: int
    resend_available_in: int
