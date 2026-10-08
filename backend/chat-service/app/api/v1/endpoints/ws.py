"""WebSocket: события чата в реальном времени.

Протокол (JSON-сообщения):

Клиент → сервер
    {"type": "auth", "token": "<access token>"}       первым сообщением
                                                      (не нужно, если токен в cookie)
    {"type": "message.send", "conversation_id", "text", "attachment_ids", "client_id"}
    {"type": "typing", "conversation_id"}
    {"type": "read", "conversation_id", "message_id"?}
    {"type": "ping"}

Сервер → клиент
    {"type": "ready", "user_id"}
    {"type": "message.ack", "client_id", "message"}   ответ на message.send
    {"type": "message.created", "message"}
    {"type": "conversation.read", "conversation_id", "user_id", "last_read_at"}
    {"type": "conversation.updated", "conversation"}
    {"type": "typing", "conversation_id", "user_id"}
    {"type": "task.updated", "task"}
    {"type": "error", "code", "message", "client_id"?}
    {"type": "ping"} / {"type": "pong"}

Токен передаётся сообщением, а не в URL, чтобы не попадать в логи прокси.
В режиме cookie браузер сам отправляет ``benefit_access`` при подключении.
"""

import asyncio
import contextlib
import logging
import time
import uuid
from collections import deque
from typing import Any

from benefit_common.cookies import access_token_from_cookie, origin_trusted
from benefit_common.errors import AppError
from benefit_common.security import Principal, TokenError, verify_access_token
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.config import settings
from app.db.session import async_session_factory
from app.schemas.chat import MessageCreate
from app.services.chat import ChatService, message_response
from app.services.realtime import hub
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter()

# Коды закрытия (диапазон 4000–4999 — для приложений).
CLOSE_UNAUTHORIZED = 4401
CLOSE_RATE_LIMITED = 4429

# Не больше N сообщений клиента за окно; при злостном превышении — разрыв.
RATE_LIMIT_MESSAGES = 30
RATE_LIMIT_WINDOW_SECONDS = 10.0
RATE_LIMIT_STRIKES = 3


class RateLimiter:
    def __init__(self) -> None:
        self.events: deque[float] = deque()
        self.strikes = 0

    def allow(self) -> bool:
        now = time.monotonic()
        while self.events and now - self.events[0] > RATE_LIMIT_WINDOW_SECONDS:
            self.events.popleft()
        if len(self.events) >= RATE_LIMIT_MESSAGES:
            self.strikes += 1
            return False
        self.events.append(now)
        return True


async def _authenticate(websocket: WebSocket) -> Principal | None:
    """Авторизация по cookie (браузер отправляет её при подключении) или
    первым сообщением ``auth``.

    По cookie принимаются только подключения с доверенного Origin: иначе
    чужой сайт мог бы открыть WebSocket от имени пользователя.
    """
    token = access_token_from_cookie(websocket.cookies)
    if token is not None:
        if not origin_trusted(websocket.headers):
            return None
        try:
            return await verify_access_token(token)
        except TokenError:
            return None
    try:
        message = await asyncio.wait_for(
            websocket.receive_json(), timeout=settings.ws_auth_timeout_seconds
        )
        if message.get("type") != "auth" or not isinstance(message.get("token"), str):
            return None
        return await verify_access_token(message["token"])
    except (TimeoutError, ValueError, TokenError, WebSocketDisconnect, AttributeError):
        return None


async def _handle(
    principal: Principal, message: dict[str, Any]
) -> dict[str, Any] | None:
    kind = message.get("type")
    if kind == "ping":
        return {"type": "pong"}
    async with async_session_factory() as session:
        chat = ChatService(session, get_storage())
        conversation_id = uuid.UUID(str(message.get("conversation_id")))
        if kind == "message.send":
            data = MessageCreate.model_validate(
                {
                    k: message[k]
                    for k in ("text", "attachment_ids", "client_id")
                    if k in message
                }
            )
            sent = await chat.send(principal, conversation_id, data)
            return {
                "type": "message.ack",
                "client_id": data.client_id,
                "message": message_response(sent).model_dump(mode="json"),
            }
        if kind == "typing":
            await chat.typing(principal, conversation_id)
            return None
        if kind == "read":
            message_id = message.get("message_id")
            await chat.mark_read(
                principal,
                conversation_id,
                uuid.UUID(str(message_id)) if message_id else None,
            )
            return None
    raise AppError("Неизвестный тип сообщения", code="unknown_type", status_code=400)


async def _ping(websocket: WebSocket) -> None:
    """Пинги держат соединение живым через прокси и балансировщики."""
    while True:
        await asyncio.sleep(settings.ws_ping_interval_seconds)
        await websocket.send_json({"type": "ping"})


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    principal = await _authenticate(websocket)
    if principal is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED, reason="unauthorized")
        return

    hub.connect(principal.id, websocket)
    pinger = asyncio.create_task(_ping(websocket))
    try:
        await websocket.send_json({"type": "ready", "user_id": str(principal.id)})
        limiter = RateLimiter()
        while True:
            try:
                message = await websocket.receive_json()
            except ValueError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "invalid_json",
                        "message": "Ожидается JSON",
                    }
                )
                continue
            if not isinstance(message, dict):
                continue
            if not limiter.allow():
                if limiter.strikes >= RATE_LIMIT_STRIKES:
                    await websocket.close(
                        code=CLOSE_RATE_LIMITED, reason="rate limited"
                    )
                    return
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "rate_limited",
                        "message": "Слишком много сообщений, подождите немного",
                    }
                )
                continue
            try:
                reply = await _handle(principal, message)
            except AppError as exc:
                reply = {"type": "error", "code": exc.code, "message": exc.message}
            except (ValidationError, ValueError, TypeError) as exc:
                reply = {
                    "type": "error",
                    "code": "invalid_request",
                    "message": str(exc)[:300],
                }
            if reply is not None:
                if "client_id" in message and reply["type"] == "error":
                    reply["client_id"] = message["client_id"]
                await websocket.send_json(reply)
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(principal.id, websocket)
        pinger.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pinger
