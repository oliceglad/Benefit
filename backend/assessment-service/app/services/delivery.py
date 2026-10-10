"""Доставка результатов в другие сервисы (через outbox).

* ``candidate.assessment`` — категория и подтверждённый грейд в профиль
  (candidate-service);
* ``candidate.skill`` — подтверждённый уровень навыка в профиль
  (candidate-service);
* ``notification`` — уведомление кандидату о результате
  (notification-service, дублируется на почту).
"""

from typing import Any

from benefit_common.internal import InternalClient
from benefit_common.outbox import OutboxRelay, PermanentDeliveryError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import OutboxMessage

CANDIDATE_ASSESSMENT = "candidate.assessment"
CANDIDATE_SKILL = "candidate.skill"
NOTIFICATION = "notification"
CHAT_MESSAGE = "chat.message"
CANDIDATE_ACTIVITY = "candidate.activity"


def _check(response: Any) -> None:
    if response.status_code == 404:
        raise PermanentDeliveryError(response.text[:500])
    if 400 <= response.status_code < 500:
        # Ошибка контракта между сервисами: повтор не поможет.
        raise PermanentDeliveryError(response.text[:500])


class CandidatePublisher:
    def __init__(self, client: InternalClient) -> None:
        self.client = client

    async def __call__(self, payload: dict[str, Any]) -> None:
        body = {k: v for k, v in payload.items() if k != "user_id"}
        response = await self.client.put(
            f"/internal/v1/candidates/{payload['user_id']}/assessment", json=body
        )
        _check(response)


class SkillPublisher:
    def __init__(self, client: InternalClient) -> None:
        self.client = client

    async def __call__(self, payload: dict[str, Any]) -> None:
        body = {k: v for k, v in payload.items() if k != "user_id"}
        response = await self.client.put(
            f"/internal/v1/candidates/{payload['user_id']}/skill-verifications",
            json=body,
        )
        _check(response)


class NotificationPublisher:
    def __init__(self, client: InternalClient) -> None:
        self.client = client

    async def __call__(self, payload: dict[str, Any]) -> None:
        response = await self.client.post("/internal/v1/notifications", json=payload)
        _check(response)


class ChatMessagePublisher:
    """Сообщение о тесте работодателя в переписку (chat-service)."""

    def __init__(self, client: InternalClient) -> None:
        self.client = client

    async def __call__(self, payload: dict[str, Any]) -> None:
        body = {k: v for k, v in payload.items() if k != "conversation_id"}
        response = await self.client.post(
            f"/internal/v1/conversations/{payload['conversation_id']}/messages",
            json=body,
        )
        _check(response)


class ActivityPublisher:
    """Активность кандидата для актуальности профиля (candidate-service)."""

    def __init__(self, client: InternalClient) -> None:
        self.client = client

    async def __call__(self, payload: dict[str, Any]) -> None:
        body = {k: v for k, v in payload.items() if k != "user_id"}
        response = await self.client.put(
            f"/internal/v1/candidates/{payload['user_id']}/activities", json=body
        )
        _check(response)


def build_relay(
    session_factory: async_sessionmaker[AsyncSession],
    candidate: Any = None,
    notification: Any = None,
    chat: Any = None,
    activity: Any = None,
    skill: Any = None,
) -> OutboxRelay:
    return OutboxRelay(
        OutboxMessage,
        session_factory,
        {
            CANDIDATE_ASSESSMENT: candidate
            or CandidatePublisher(
                InternalClient(settings.candidate_service_url, service="candidate")
            ),
            CANDIDATE_SKILL: skill
            or SkillPublisher(
                InternalClient(settings.candidate_service_url, service="candidate")
            ),
            NOTIFICATION: notification
            or NotificationPublisher(
                InternalClient(
                    settings.notification_service_url, service="notification"
                )
            ),
            CHAT_MESSAGE: chat
            or ChatMessagePublisher(
                InternalClient(settings.chat_service_url, service="chat")
            ),
            CANDIDATE_ACTIVITY: activity
            or ActivityPublisher(
                InternalClient(settings.candidate_service_url, service="candidate")
            ),
        },
    )
