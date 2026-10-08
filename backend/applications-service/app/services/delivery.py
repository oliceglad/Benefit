"""Доставка уведомлений участникам приглашения (через outbox)."""

from typing import Any

from benefit_common.internal import InternalClient
from benefit_common.outbox import OutboxRelay, PermanentDeliveryError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import OutboxMessage

NOTIFICATION = "notification"
CONTACT_GRANT = "candidate.contact_grant"
CHAT_SYNC = "chat.conversation"


class NotificationPublisher:
    def __init__(self, client: InternalClient) -> None:
        self.client = client

    async def __call__(self, payload: dict[str, Any]) -> None:
        response = await self.client.post("/internal/v1/notifications", json=payload)
        if 400 <= response.status_code < 500:
            raise PermanentDeliveryError(response.text[:500])


class ContactGrantPublisher:
    """Открывает работодателю контакты кандидата в candidate-service."""

    def __init__(self, client: InternalClient) -> None:
        self.client = client

    async def __call__(self, payload: dict[str, Any]) -> None:
        response = await self.client.put(
            f"/internal/v1/candidates/{payload['candidate_id']}/contact-grants",
            json={
                "employer_id": payload["employer_id"],
                "source": payload["source"],
                "source_id": payload["source_id"],
            },
        )
        if 400 <= response.status_code < 500:
            # Например, кандидат удалил профиль: открывать уже нечего.
            raise PermanentDeliveryError(response.text[:500])


class ChatPublisher:
    """Создаёт диалог по приглашению и синхронизирует его статус."""

    def __init__(self, client: InternalClient) -> None:
        self.client = client

    async def __call__(self, payload: dict[str, Any]) -> None:
        response = await self.client.put("/internal/v1/conversations", json=payload)
        if 400 <= response.status_code < 500:
            raise PermanentDeliveryError(response.text[:500])


def build_relay(
    session_factory: async_sessionmaker[AsyncSession],
    notification: Any = None,
    contact_grant: Any = None,
    chat: Any = None,
) -> OutboxRelay:
    return OutboxRelay(
        OutboxMessage,
        session_factory,
        {
            NOTIFICATION: notification
            or NotificationPublisher(
                InternalClient(
                    settings.notification_service_url, service="notification"
                )
            ),
            CONTACT_GRANT: contact_grant
            or ContactGrantPublisher(
                InternalClient(settings.candidate_service_url, service="candidate")
            ),
            CHAT_SYNC: chat
            or ChatPublisher(InternalClient(settings.chat_service_url, service="chat")),
        },
    )
