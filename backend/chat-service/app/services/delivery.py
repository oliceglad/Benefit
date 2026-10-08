"""Сообщения в другие сервисы через outbox.

* ``notification`` — уведомления участникам (notification-service);
* ``candidate.activity`` — активность кандидата по заданиям
  (candidate-service): влияет на актуальность профиля.
"""

import uuid
from datetime import datetime
from typing import Any

from benefit_common.internal import InternalClient
from benefit_common.outbox import OutboxRelay, PermanentDeliveryError, enqueue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import OutboxMessage

NOTIFICATION = "notification"
CANDIDATE_ACTIVITY = "candidate.activity"


def notify(
    session: AsyncSession,
    user_id: uuid.UUID,
    event: str,
    title: str,
    body: str,
    link: str,
    dedup_key: str,
    *,
    email: bool = True,
    data: dict[str, Any] | None = None,
) -> None:
    enqueue(
        session,
        OutboxMessage,
        NOTIFICATION,
        {
            "user_id": str(user_id),
            "type": event,
            "title": title[:200],
            "body": body[:5000],
            "link": link,
            "data": data or {},
            "email": email,
            "dedup_key": dedup_key,
        },
    )


def record_activity(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    kind: str,
    ref_id: uuid.UUID,
    occurred_at: datetime,
    data: dict[str, Any] | None = None,
) -> None:
    enqueue(
        session,
        OutboxMessage,
        CANDIDATE_ACTIVITY,
        {
            "user_id": str(candidate_id),
            "kind": kind,
            "ref_id": str(ref_id),
            "occurred_at": occurred_at.isoformat(),
            "data": data or {},
        },
    )


class NotificationPublisher:
    def __init__(self, client: InternalClient) -> None:
        self.client = client

    async def __call__(self, payload: dict[str, Any]) -> None:
        response = await self.client.post("/internal/v1/notifications", json=payload)
        if 400 <= response.status_code < 500:
            raise PermanentDeliveryError(response.text[:500])


class ActivityPublisher:
    def __init__(self, client: InternalClient) -> None:
        self.client = client

    async def __call__(self, payload: dict[str, Any]) -> None:
        body = {k: v for k, v in payload.items() if k != "user_id"}
        response = await self.client.put(
            f"/internal/v1/candidates/{payload['user_id']}/activities", json=body
        )
        if 400 <= response.status_code < 500:
            # Профиль удалён — учитывать активность негде.
            raise PermanentDeliveryError(response.text[:500])


def build_relay(
    session_factory: async_sessionmaker[AsyncSession],
    notification: Any = None,
    activity: Any = None,
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
            CANDIDATE_ACTIVITY: activity
            or ActivityPublisher(
                InternalClient(settings.candidate_service_url, service="candidate")
            ),
        },
    )
