"""Регистрация и вход по почте и паролю."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AppError,
    ConflictError,
    ForbiddenError,
    UnauthorizedError,
)
from app.core.security import hash_password, verify_password
from app.models.tokens import CodePurpose
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import RegisterRequest, RegisterResponse, TokenResponse
from app.services.codes import OneTimeCodes, invalid_code
from app.services.email_policy import is_email_domain_allowed
from app.services.mail_client import MailClient
from app.services.tokens import TokenService

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession, mail: MailClient) -> None:
        self.session = session
        self.mail = mail
        self.users = UserRepository(session)
        self.tokens = TokenService(session)
        self.codes = OneTimeCodes(session, mail)

    async def register(self, data: RegisterRequest) -> RegisterResponse:
        if not is_email_domain_allowed(data.email):
            raise AppError(
                "Регистрация доступна только для почты в российских доменах",
                code="email_domain_not_allowed",
                status_code=422,
            )

        user = await self.users.get_by_email(data.email)
        if user is not None and (user.is_email_verified or user.password_hash is None):
            raise ConflictError(
                "Пользователь с такой почтой уже зарегистрирован", code="email_taken"
            )

        if user is not None:
            # Пока действует код, повторная регистрация запрещена: иначе
            # злоумышленник подменил бы пароль, а владелец почты подтвердил
            # бы чужую регистрацию присланным ему кодом.
            pending = await self.codes.latest(user, CodePurpose.VERIFY_EMAIL)
            if pending is not None and pending.expires_at > datetime.now(UTC):
                raise ConflictError(
                    "На эту почту уже отправлен код подтверждения. Введите его "
                    "или запросите новый код",
                    code="registration_pending",
                )
        if user is None:
            user = User(email=data.email)
            self.session.add(user)
        # После истечения кода регистрацию можно повторить (например, если
        # письмо не дошло): обновляем данные и высылаем новый код.
        user.password_hash = hash_password(data.password)
        user.role = data.role
        user.full_name = data.full_name
        await self.session.flush()

        await self._send_code(user)
        return RegisterResponse(
            email=user.email,
            code_expires_in=settings.verification_code_ttl_minutes * 60,
            resend_available_in=settings.verification_resend_cooldown_seconds,
        )

    async def resend_code(self, email: str) -> None:
        """Повторная отправка кода. Для несуществующих и уже подтверждённых
        адресов молча ничего не делает, чтобы не раскрывать наличие аккаунта."""
        user = await self.users.get_by_email(email)
        if user is None or user.is_email_verified or user.password_hash is None:
            return

        await self.codes.ensure_can_send(user, CodePurpose.VERIFY_EMAIL)
        await self._send_code(user)

    async def verify_email(self, email: str, code: str) -> TokenResponse:
        user = await self.users.get_by_email(email)
        if user is None:
            raise invalid_code()
        if user.is_email_verified:
            raise ConflictError("Почта уже подтверждена", code="already_verified")

        await self.codes.verify(user, CodePurpose.VERIFY_EMAIL, code)
        user.email_verified_at = datetime.now(UTC)
        await self.codes.discard(user, CodePurpose.VERIFY_EMAIL)
        tokens = await self.tokens.issue(user)
        await self.session.commit()
        return tokens

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self.users.get_by_email(email)
        now = datetime.now(UTC)
        if user is not None and user.locked_until and user.locked_until > now:
            # Блокировка проверяется до пароля: перебор не продолжается.
            retry_after = int((user.locked_until - now).total_seconds()) + 1
            raise AppError(
                "Слишком много неудачных попыток входа. Повторите через "
                f"{retry_after // 60 + 1} мин.",
                code="account_locked",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
            )
        password_hash = user.password_hash if user else None
        if not verify_password(password, password_hash) or user is None:
            if user is not None:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= settings.login_max_failures:
                    user.locked_until = now + timedelta(
                        minutes=settings.login_lock_minutes
                    )
                    user.failed_login_attempts = 0
                await self.session.commit()
            raise UnauthorizedError(
                "Неверная почта или пароль", code="invalid_credentials"
            )
        user.failed_login_attempts = 0
        user.locked_until = None
        if not user.is_active:
            raise ForbiddenError("Аккаунт заблокирован", code="account_disabled")
        if not user.is_email_verified:
            raise ForbiddenError("Почта не подтверждена", code="email_not_verified")

        tokens = await self.tokens.issue(user)
        await self.session.commit()
        return tokens

    async def _send_code(self, user: User) -> None:
        """Заменяет действующий код новым и отправляет его на почту."""
        await self.codes.issue(
            user,
            CodePurpose.VERIFY_EMAIL,
            to=user.email,
            ttl_minutes=settings.verification_code_ttl_minutes,
        )
