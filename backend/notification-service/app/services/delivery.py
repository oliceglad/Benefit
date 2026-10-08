"""Доставка уведомлений на почту через mail-service."""

import logging
import uuid
from typing import Any

from benefit_common.internal import InternalClient
from benefit_common.outbox import OutboxRelay, PermanentDeliveryError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import EmailDelivery

logger = logging.getLogger(__name__)

EMAIL_KIND = "email"


class EmailSender:
    """Узнаёт адрес пользователя в auth-service и отправляет письмо."""

    def __init__(self, auth: InternalClient, mail: InternalClient) -> None:
        self.auth = auth
        self.mail = mail

    async def __call__(self, payload: dict[str, Any]) -> None:
        user = await self.auth.get(f"/internal/v1/users/{payload['user_id']}")
        if user.status_code == 404:
            raise PermanentDeliveryError("user not found")
        user.raise_for_status()
        account = user.json()
        if not account["is_active"]:
            raise PermanentDeliveryError("user is inactive")

        link = payload.get("link")
        response = await self.mail.post(
            "/api/v1/emails/notification",
            json={
                "to": account["email"],
                "subject": payload["title"],
                "title": payload["title"],
                "body": payload["body"],
                "action_url": f"{settings.frontend_url}{link}" if link else None,
                "action_label": payload.get("action_label") or "Открыть в Benefit",
            },
        )
        if 400 <= response.status_code < 500:
            # Повтор не поможет: письмо некорректно (например, адрес).
            raise PermanentDeliveryError(response.text[:500])
        logger.info("Email notification %s sent", payload.get("notification_id"))


def build_email_payload(
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    body: str,
    link: str | None,
) -> dict[str, Any]:
    return {
        "notification_id": str(notification_id),
        "user_id": str(user_id),
        "title": title,
        "body": body,
        "link": link,
    }


def build_relay(
    session_factory: async_sessionmaker[AsyncSession], sender: EmailSender | None = None
) -> OutboxRelay:
    sender = sender or EmailSender(
        InternalClient(settings.auth_internal_url, service="auth"),
        InternalClient(settings.mail_service_url, service="mail"),
    )
    return OutboxRelay(EmailDelivery, session_factory, {EMAIL_KIND: sender})
