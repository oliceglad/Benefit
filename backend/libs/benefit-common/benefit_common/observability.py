"""Подключение сервиса к общей инфраструктуре: сквозной request_id,
логи с ID запроса и сервиса, единый формат ошибок."""

import logging
import re
import sys
import uuid
from typing import Any

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from benefit_common.context import (
    REQUEST_ID_HEADER,
    request_id_var,
    service_name_var,
)
from benefit_common.errors import register_exception_handlers, unhandled_error_handler
from benefit_common.settings import get_common_settings

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(service)s | %(request_id)s "
    "| %(name)s | %(message)s"
)
# Принимаем ID от шлюза или клиента, только если он безопасен для логов.
VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


class ContextFilter(logging.Filter):
    """Добавляет в каждую запись лога ID запроса и имя сервиса."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        record.service = service_name_var.get()
        return True


def configure_logging(level: str, service: str) -> None:
    service_name_var.set(service)
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ContextFilter())
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)


class RequestContextMiddleware:
    """Берёт ``X-Request-ID`` из запроса (или создаёт) и возвращает его
    в ответе. ID передаётся во все межсервисные вызовы (InternalClient)."""

    def __init__(self, app: ASGIApp, service: str) -> None:
        self.app = app
        self.service = service

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(
            REQUEST_ID_HEADER.lower().encode()
        )
        value = incoming.decode("latin-1") if incoming else ""
        request_id = value if VALID_REQUEST_ID.match(value) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        service_token = service_name_var.set(self.service)

        started = False

        async def send_with_id(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers: list[Any] = list(message.get("headers") or [])
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception as exc:
            # Непредвиденная ошибка: понятный JSON с request_id вместо
            # «Internal Server Error» (стектрейс — в лог).
            if scope["type"] != "http" or started:
                raise
            response = await unhandled_error_handler(None, exc)  # type: ignore[arg-type]
            await response(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)
            service_name_var.reset(service_token)


def setup_app(app: FastAPI, service: str) -> None:
    """Единые обработчики ошибок и сквозной request_id для сервиса.

    Проверяет конфигурацию: в production с небезопасными настройками
    сервис не запустится.
    """
    service_name_var.set(service)
    # Валидация настроек: в production небезопасная конфигурация — ошибка.
    get_common_settings()
    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware, service=service)
