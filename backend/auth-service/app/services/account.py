"""Жизненный цикл аккаунта: восстановление и смена пароля, смена почты,
редактирование и удаление.

Чувствительные действия подтверждаются паролем или кодом из письма. Смена
пароля и почты завершает остальные сессии (refresh-токены отзываются), а
владельцу приходит письмо — так он узнает о чужих действиях.
"""

import logging
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, ConflictError
from app.core.security import hash_password, verify_password
from app.models.tokens import CodePurpose
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.account import CodeSent
from app.schemas.auth import TokenResponse
from app.services.codes import OneTimeCodes
from app.services.deletion import enqueue_deletion
from app.services.email_policy import is_email_domain_allowed
from app.services.mail_client import MailClient, MailDeliveryError
from app.services.tokens import TokenService

logger = logging.getLogger(__name__)


def _wrong_password() -> AppError:
    return AppError(
        "Неверный текущий пароль",
        code="invalid_password",
        status_code=status.HTTP_403_FORBIDDEN,
    )


class AccountService:
    def __init__(self, session: AsyncSession, mail: MailClient) -> None:
        self.session = session
        self.mail = mail
        self.users = UserRepository(session)
        self.tokens = TokenService(session)
        self.codes = OneTimeCodes(session, mail)

    # --- Восстановление пароля ---------------------------------------------------

    async def forgot_password(self, email: str) -> None:
        """Код сброса на почту. Для неизвестных адресов ничего не делает и
        отвечает так же, чтобы не раскрывать наличие аккаунта."""
        user = await self.users.get_by_email(email)
        if user is None or not user.is_active:
            return
        # Повторный запрос раньше времени молча игнорируется: ошибка
        # выдала бы, что аккаунт существует.
        if await self.codes.retry_after(user, CodePurpose.RESET_PASSWORD):
            return
        await self.codes.issue(
            user,
            CodePurpose.RESET_PASSWORD,
            to=user.email,
            ttl_minutes=settings.account_code_ttl_minutes,
        )

    async def reset_password(self, email: str, code: str, new_password: str) -> None:
        """Новый пароль по коду из письма. Все сессии завершаются.

        Код подтверждает владение почтой, поэтому неподтверждённая почта
        становится подтверждённой (а пароль, заданный при регистрации кем-то
        другим, — заменён).
        """
        user = await self.users.get_by_email(email)
        if user is None or not user.is_active:
            raise AppError("Неверный код подтверждения", code="invalid_code")
        await self.codes.verify(user, CodePurpose.RESET_PASSWORD, code)
        user.password_hash = hash_password(new_password)
        if not user.is_email_verified:
            user.email_verified_at = datetime.now(UTC)
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.codes.discard(user)
        await self.tokens.end_sessions(user.id)
        await self.session.commit()
        await self._inform(
            user.email,
            "Benefit: пароль изменён",
            "Пароль от вашего аккаунта Benefit был восстановлен по коду из письма. "
            "Все остальные сессии завершены.\n\nЕсли это были не вы, сразу "
            "восстановите пароль ещё раз и проверьте доступ к почте.",
        )

    # --- Смена пароля --------------------------------------------------------------

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> TokenResponse:
        """Смена пароля с подтверждением текущим. Остальные сессии
        завершаются, текущая получает новую пару токенов."""
        if user.password_hash is None:
            raise ConflictError(
                "У аккаунта нет пароля (вход через ФСП ID или Keycloak). Задайте "
                "пароль через восстановление пароля",
                code="password_not_set",
            )
        if not verify_password(current_password, user.password_hash):
            raise _wrong_password()
        if verify_password(new_password, user.password_hash):
            raise AppError(
                "Новый пароль совпадает с текущим",
                code="same_password",
                status_code=422,
            )
        user.password_hash = hash_password(new_password)
        await self.tokens.end_sessions(user.id)
        tokens = await self.tokens.issue(user)
        await self.session.commit()
        await self._inform(
            user.email,
            "Benefit: пароль изменён",
            "Пароль от вашего аккаунта Benefit изменён, остальные сессии "
            "завершены.\n\nЕсли это были не вы, восстановите пароль по почте.",
        )
        return tokens

    # --- Профиль и почта -------------------------------------------------------------

    async def update_profile(self, user: User, full_name: str | None) -> User:
        user.full_name = full_name
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def request_email_change(
        self, user: User, new_email: str, password: str | None
    ) -> CodeSent:
        """Код подтверждения уходит на новый адрес; почта меняется только
        после ввода кода."""
        self._confirm_password(user, password)
        if new_email == user.email:
            raise AppError("Это ваш текущий адрес", code="same_email", status_code=422)
        if not is_email_domain_allowed(new_email):
            raise AppError(
                "Можно указать только почту в российских доменах",
                code="email_domain_not_allowed",
                status_code=422,
            )
        if await self.users.get_by_email(new_email) is not None:
            raise ConflictError(
                "Пользователь с такой почтой уже зарегистрирован", code="email_taken"
            )
        await self.codes.ensure_can_send(user, CodePurpose.CHANGE_EMAIL)
        await self.codes.issue(
            user,
            CodePurpose.CHANGE_EMAIL,
            to=new_email,
            new_email=new_email,
            ttl_minutes=settings.account_code_ttl_minutes,
        )
        return self._code_sent(new_email)

    async def confirm_email_change(self, user: User, code: str) -> TokenResponse:
        stored = await self.codes.verify(user, CodePurpose.CHANGE_EMAIL, code)
        new_email = stored.new_email
        assert new_email is not None
        if await self.users.get_by_email(new_email) is not None:
            raise ConflictError(
                "Пользователь с такой почтой уже зарегистрирован", code="email_taken"
            )
        old_email = user.email
        user.email = new_email
        user.email_verified_at = datetime.now(UTC)
        await self.codes.discard(user, CodePurpose.CHANGE_EMAIL)
        # В access-токене почта — выдаём новую пару, прочие сессии завершаем.
        await self.tokens.end_sessions(user.id)
        tokens = await self.tokens.issue(user)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(
                "Пользователь с такой почтой уже зарегистрирован", code="email_taken"
            ) from exc
        await self._inform(
            old_email,
            "Benefit: адрес почты изменён",
            f"Адрес почты вашего аккаунта Benefit изменён на {new_email}. "
            "Письма теперь приходят на новый адрес.\n\nЕсли это были не вы, "
            "обратитесь в поддержку.",
        )
        return tokens

    # --- Удаление ------------------------------------------------------------------

    async def send_deletion_code(self, user: User) -> CodeSent:
        await self.codes.ensure_can_send(user, CodePurpose.DELETE_ACCOUNT)
        await self.codes.issue(
            user,
            CodePurpose.DELETE_ACCOUNT,
            to=user.email,
            ttl_minutes=settings.account_code_ttl_minutes,
        )
        return self._code_sent(user.email)

    async def delete(self, user: User, password: str | None, code: str | None) -> None:
        """Удаляет аккаунт и запускает удаление данных во всех сервисах.

        Подтверждение — пароль или код из письма (для аккаунтов без пароля
        — только код).
        """
        if password is not None and user.password_hash is not None:
            if not verify_password(password, user.password_hash):
                raise _wrong_password()
        elif code is not None:
            await self.codes.verify(user, CodePurpose.DELETE_ACCOUNT, code)
        else:
            raise AppError(
                "Подтвердите удаление паролем или кодом из письма",
                code="confirmation_required",
                status_code=422,
            )
        email = user.email
        enqueue_deletion(self.session, user.id, user.role.value)
        # Каскадом удаляются refresh-токены, коды и привязанные аккаунты.
        await self.session.delete(user)
        await self.session.commit()
        logger.info("Account %s deleted", user.id)
        await self._inform(
            email,
            "Benefit: аккаунт удалён",
            "Ваш аккаунт Benefit и связанные с ним данные удалены.",
        )

    # --- Внутреннее ------------------------------------------------------------------

    def _confirm_password(self, user: User, password: str | None) -> None:
        if user.password_hash is None:
            return
        if password is None:
            raise AppError(
                "Введите текущий пароль", code="password_required", status_code=422
            )
        if not verify_password(password, user.password_hash):
            raise _wrong_password()

    @staticmethod
    def _code_sent(email: str) -> CodeSent:
        return CodeSent(
            email=email,
            code_expires_in=settings.account_code_ttl_minutes * 60,
            resend_available_in=settings.verification_resend_cooldown_seconds,
        )

    async def _inform(self, to: str, subject: str, body: str) -> None:
        """Информационное письмо: его сбой не отменяет уже выполненное действие."""
        try:
            await self.mail.send_notification(to=to, subject=subject, body=body)
        except MailDeliveryError:
            logger.warning("Failed to send account notice to user")
