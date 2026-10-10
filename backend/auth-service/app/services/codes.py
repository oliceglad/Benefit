"""Одноразовые коды из писем: подтверждение почты, сброс пароля, смена
почты, удаление аккаунта.

В БД хранится только HMAC кода. У пользователя действует не больше одного
кода каждого назначения; число попыток ввода ограничено.
"""

import hmac
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, ServiceUnavailableError
from app.core.security import generate_verification_code, hash_verification_code
from app.models.tokens import CodePurpose, EmailVerificationCode
from app.models.user import User
from app.services.mail_client import MailClient, MailDeliveryError


def invalid_code() -> AppError:
    return AppError("Неверный код подтверждения", code="invalid_code")


class OneTimeCodes:
    def __init__(self, session: AsyncSession, mail: MailClient) -> None:
        self.session = session
        self.mail = mail

    async def latest(
        self, user: User, purpose: CodePurpose, *, lock: bool = False
    ) -> EmailVerificationCode | None:
        query = (
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.user_id == user.id,
                EmailVerificationCode.purpose == purpose,
            )
            .order_by(EmailVerificationCode.created_at.desc())
            .limit(1)
        )
        if lock:
            # Параллельные запросы не обойдут лимит попыток.
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def retry_after(self, user: User, purpose: CodePurpose) -> int:
        """Сколько секунд ждать до повторной отправки (0 — можно сейчас)."""
        last = await self.latest(user, purpose)
        if last is None:
            return 0
        cooldown = timedelta(seconds=settings.verification_resend_cooldown_seconds)
        left = cooldown - (datetime.now(UTC) - last.created_at)
        return int(left.total_seconds()) + 1 if left.total_seconds() > 0 else 0

    async def ensure_can_send(self, user: User, purpose: CodePurpose) -> None:
        retry_after = await self.retry_after(user, purpose)
        if retry_after:
            raise AppError(
                f"Повторно запросить код можно через {retry_after} с",
                code="resend_cooldown",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
            )

    async def issue(
        self,
        user: User,
        purpose: CodePurpose,
        *,
        to: str,
        ttl_minutes: int,
        new_email: str | None = None,
    ) -> None:
        """Заменяет действующий код новым и отправляет его на ``to``.

        Коммитит транзакцию: код сохраняется до отправки письма.
        """
        code = generate_verification_code()
        await self.discard(user, purpose)
        self.session.add(
            EmailVerificationCode(
                user_id=user.id,
                purpose=purpose,
                new_email=new_email,
                code_hash=hash_verification_code(code),
                expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
            )
        )
        await self.session.commit()
        try:
            await self.mail.send_verification_code(
                to=to, code=code, ttl_minutes=ttl_minutes, purpose=purpose.value
            )
        except MailDeliveryError as exc:
            # Код не доставлен — удаляем его, чтобы запрос можно было
            # сразу повторить.
            await self.discard(user, purpose)
            await self.session.commit()
            raise ServiceUnavailableError(
                "Не удалось отправить письмо, запросите код повторно позже",
                code="mail_unavailable",
            ) from exc

    async def verify(
        self, user: User, purpose: CodePurpose, code: str
    ) -> EmailVerificationCode:
        """Проверяет код. Неверный ввод увеличивает счётчик попыток
        (с коммитом); удалить использованный код — задача вызывающего."""
        stored = await self.latest(user, purpose, lock=True)
        if stored is None:
            raise invalid_code()
        if stored.expires_at <= datetime.now(UTC):
            raise AppError(
                "Срок действия кода истёк, запросите новый", code="code_expired"
            )
        if stored.attempts >= settings.verification_code_max_attempts:
            raise AppError(
                "Превышено число попыток, запросите новый код",
                code="too_many_attempts",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if not hmac.compare_digest(stored.code_hash, hash_verification_code(code)):
            stored.attempts += 1
            await self.session.commit()
            raise invalid_code()
        return stored

    async def discard(self, user: User, purpose: CodePurpose | None = None) -> None:
        """Удаляет коды пользователя (все или одного назначения)."""
        query = delete(EmailVerificationCode).where(
            EmailVerificationCode.user_id == user.id
        )
        if purpose is not None:
            query = query.where(EmailVerificationCode.purpose == purpose)
        await self.session.execute(query)
