"""Удаление аккаунта во всех сервисах.

Аккаунт удаляется в auth-service сразу, а каждому сервису, который хранит
данные пользователя, в той же транзакции записывается событие в outbox.
``OutboxRelay`` доставляет его во внутренний API сервиса
(``DELETE /internal/v1/users/{id}``) и повторяет при сбоях, пока сервис не
подтвердит удаление. Обработчики в сервисах идемпотентны.
"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from benefit_common.internal import InternalClient
from benefit_common.outbox import OutboxRelay, PermanentDeliveryError, enqueue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.outbox import OutboxMessage

KIND_PREFIX = "user.deleted:"
# Попыток много: удаление персональных данных нельзя «потерять», даже если
# сервис долго недоступен (интервал между попытками растёт до 10 минут).
MAX_ATTEMPTS = 200


def targets() -> dict[str, str]:
    """Сервис → его адрес во внутренней сети."""
    return {
        "candidate": settings.candidate_service_url,
        "employer": settings.employer_service_url,
        "applications": settings.applications_service_url,
        "chat": settings.chat_service_url,
        "notification": settings.notification_service_url,
        "assessment": settings.assessment_service_url,
        "matching": settings.matching_service_url,
    }


def enqueue_deletion(session: AsyncSession, user_id: uuid.UUID, role: str) -> None:
    """Событие удаления для каждого сервиса (коммит — у вызывающего)."""
    for service in targets():
        enqueue(
            session,
            OutboxMessage,
            f"{KIND_PREFIX}{service}",
            {"user_id": str(user_id), "role": role},
        )


def _handler(client: InternalClient) -> Callable[[dict[str, Any]], Awaitable[None]]:
    async def deliver(payload: dict[str, Any]) -> None:
        response = await client.delete(
            f"/internal/v1/users/{payload['user_id']}",
            params={"role": payload["role"]},
        )
        if response.status_code in (200, 202, 204, 404):
            return
        # 4xx — ошибка в запросе: повтор не поможет, нужен разбор вручную.
        raise PermanentDeliveryError(response.text[:500])

    return deliver


def build_relay(
    session_factory: async_sessionmaker[AsyncSession],
    handlers: dict[str, Callable[[dict[str, Any]], Awaitable[None]]] | None = None,
) -> OutboxRelay:
    return OutboxRelay(
        OutboxMessage,
        session_factory,
        handlers
        or {
            f"{KIND_PREFIX}{service}": _handler(InternalClient(url, service=service))
            for service, url in targets().items()
        },
        max_attempts=MAX_ATTEMPTS,
    )
