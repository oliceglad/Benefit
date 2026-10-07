"""Отправка писем по SMTP."""

import logging
from email.message import EmailMessage
from typing import Protocol

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


class MailSendError(Exception):
    pass


class MailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class SmtpSender:
    async def send(self, message: EmailMessage) -> None:
        try:
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                # Пустые значения из окружения означают «без авторизации».
                username=settings.smtp_username or None,
                password=settings.smtp_password or None,
                use_tls=settings.smtp_use_tls,
                start_tls=settings.smtp_start_tls,
                timeout=settings.smtp_timeout_seconds,
            )
        except (aiosmtplib.SMTPException, OSError) as exc:
            logger.exception("SMTP delivery failed")
            raise MailSendError(str(exc)) from exc


def get_sender() -> MailSender:
    return SmtpSender()
