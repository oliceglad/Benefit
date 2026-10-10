"""Клиент mail-service."""

import logging
from typing import Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class MailDeliveryError(Exception):
    """Письмо не удалось передать в mail-service."""


class MailClient(Protocol):
    async def send_verification_code(
        self, *, to: str, code: str, ttl_minutes: int, purpose: str = "verify_email"
    ) -> None: ...

    async def send_notification(self, *, to: str, subject: str, body: str) -> None:
        """Информационное письмо (например, «пароль изменён»)."""
        ...


class HttpMailClient:
    def __init__(self, base_url: str, token: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    async def _post(self, path: str, payload: dict[str, object]) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}{path}",
                    json=payload,
                    headers={"X-Internal-Token": self.token},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("Failed to send email via %s", path)
            raise MailDeliveryError(str(exc)) from exc

    async def send_verification_code(
        self, *, to: str, code: str, ttl_minutes: int, purpose: str = "verify_email"
    ) -> None:
        await self._post(
            "/api/v1/emails/verification-code",
            {"to": to, "code": code, "ttl_minutes": ttl_minutes, "purpose": purpose},
        )

    async def send_notification(self, *, to: str, subject: str, body: str) -> None:
        await self._post(
            "/api/v1/emails/notification",
            {"to": to, "subject": subject, "title": subject, "body": body},
        )


def get_mail_client() -> MailClient:
    return HttpMailClient(settings.mail_service_url, settings.internal_api_token)
