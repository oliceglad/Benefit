"""Transactional outbox: надёжная доставка сообщений в другие сервисы.

Сообщение записывается в таблицу сервиса в той же транзакции, что и
изменение данных, а фоновый ``OutboxRelay`` доставляет его обработчику
(обычно — HTTP-вызов внутреннего API соседнего сервиса). Если соседний
сервис недоступен, доставка повторяется с экспоненциальной задержкой,
поэтому сбой одного сервиса не теряет данные и не ломает пользовательский
запрос.

Использование::

    class OutboxMessage(OutboxMessageMixin, Base):
        __tablename__ = "outbox_messages"

    enqueue(session, OutboxMessage, "notify", {...})  # до commit
    relay = OutboxRelay(OutboxMessage, session_factory, {"notify": handler})
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import BigInteger, DateTime, Identity, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class PermanentDeliveryError(Exception):
    """Повторять доставку бессмысленно (например, получатель не найден)."""


class OutboxMessageMixin:
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Доставка прекращена (исчерпаны попытки или постоянная ошибка).
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def enqueue(
    session: AsyncSession, model: type[Any], kind: str, payload: dict[str, Any]
) -> None:
    """Добавляет сообщение в текущую транзакцию (коммит — у вызывающего)."""
    session.add(model(kind=kind, payload=payload))


class OutboxRelay:
    def __init__(
        self,
        model: type[Any],
        session_factory: async_sessionmaker[AsyncSession],
        handlers: dict[str, Handler],
        *,
        interval: float = 2.0,
        batch_size: int = 20,
        max_attempts: int = 10,
        max_backoff_seconds: int = 600,
    ) -> None:
        self.model = model
        self.session_factory = session_factory
        self.handlers = handlers
        self.interval = interval
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.max_backoff_seconds = max_backoff_seconds

    def _backoff(self, attempts: int) -> timedelta:
        seconds = min(self.interval * 2**attempts, self.max_backoff_seconds)
        return timedelta(seconds=seconds)

    async def process_batch(self) -> int:
        """Доставляет готовые к отправке сообщения. Возвращает их число."""
        model = self.model
        now = datetime.now(UTC)
        async with self.session_factory() as session:
            messages = (
                await session.scalars(
                    select(model)
                    .where(
                        model.sent_at.is_(None),
                        model.failed_at.is_(None),
                        model.next_attempt_at <= now,
                    )
                    .order_by(model.id)
                    .limit(self.batch_size)
                    # Несколько реплик сервиса не возьмут одно сообщение.
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for message in messages:
                await self._deliver(message)
            await session.commit()
        return len(messages)

    async def _deliver(self, message: Any) -> None:
        handler = self.handlers.get(message.kind)
        now = datetime.now(UTC)
        if handler is None:
            message.failed_at = now
            message.last_error = f"No handler for {message.kind}"
            logger.error("Outbox: no handler for %s", message.kind)
            return
        try:
            await handler(message.payload)
        except PermanentDeliveryError as exc:
            message.failed_at = now
            message.last_error = str(exc)[:2000]
            logger.warning("Outbox %s #%s dropped: %s", message.kind, message.id, exc)
        except Exception as exc:  # noqa: BLE001 — любая ошибка = повтор
            message.attempts += 1
            message.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            if message.attempts >= self.max_attempts:
                message.failed_at = now
                logger.error("Outbox %s #%s failed: %s", message.kind, message.id, exc)
            else:
                message.next_attempt_at = now + self._backoff(message.attempts)
                logger.info(
                    "Outbox %s #%s retry %s: %s",
                    message.kind,
                    message.id,
                    message.attempts,
                    exc,
                )
        else:
            message.sent_at = now

    async def run(self) -> None:
        while True:
            try:
                processed = await self.process_batch()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outbox relay iteration failed")
                processed = 0
            if processed < self.batch_size:
                await asyncio.sleep(self.interval)

    @contextlib.asynccontextmanager
    async def running(self) -> AsyncIterator[None]:
        """Запускает доставку в фоне на время жизни приложения."""
        task = asyncio.create_task(self.run())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
