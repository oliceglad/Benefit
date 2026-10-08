"""Доставка событий в WebSocket-подключения.

Каждый экземпляр сервиса держит свои подключения, а события между
экземплярами расходятся через PostgreSQL ``LISTEN/NOTIFY``:

1. изменение (например, новое сообщение) и ``pg_notify`` выполняются в одной
   транзакции — событие уходит только после успешного коммита;
2. все экземпляры получают уведомление и отправляют событие тем
   участникам, которые подключены именно к ним.

В уведомлении передаются только идентификаторы (лимит NOTIFY — 8000 байт),
полные данные загружаются из БД при отправке.
"""

import asyncio
import contextlib
import json
import logging
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
from fastapi import WebSocket
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)

CHANNEL = "chat_events"

# Превращает уведомление в событие для клиента (с загрузкой из БД).
Resolver = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]]


async def publish(
    session: AsyncSession, users: list[uuid.UUID], event_type: str, **data: Any
) -> None:
    """Ставит событие в текущую транзакцию (уйдёт после commit)."""
    payload = json.dumps(
        {"users": [str(u) for u in users], "type": event_type, **data}, default=str
    )
    await session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": CHANNEL, "payload": payload},
    )


class Hub:
    def __init__(self) -> None:
        self.connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        self.resolver: Resolver | None = None
        self._listener: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()

    def connect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        self.connections[user_id].add(websocket)

    def disconnect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        sockets = self.connections.get(user_id)
        if sockets is not None:
            sockets.discard(websocket)
            if not sockets:
                del self.connections[user_id]

    def is_online(self, user_id: uuid.UUID) -> bool:
        return bool(self.connections.get(user_id))

    async def send(self, user_ids: list[uuid.UUID], event: dict[str, Any]) -> None:
        for user_id in user_ids:
            for websocket in list(self.connections.get(user_id, ())):
                try:
                    await websocket.send_json(event)
                except Exception:  # noqa: BLE001 — сокет уже закрыт
                    self.disconnect(user_id, websocket)

    async def _dispatch(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
            users = [uuid.UUID(u) for u in payload.pop("users")]
            local = [u for u in users if self.is_online(u)]
            if not local:
                return
            event = await self.resolver(payload) if self.resolver else payload
            if event is not None:
                await self.send(local, event)
        except Exception:
            logger.exception("Failed to dispatch realtime event")

    def _on_notify(self, _conn: Any, _pid: int, _channel: str, raw: str) -> None:
        asyncio.get_running_loop().create_task(self._dispatch(raw))

    async def _listen_forever(self) -> None:
        """Держит LISTEN-подключение, переподключаясь при обрыве."""
        dsn = settings.database_url.render_as_string(hide_password=False).replace(
            "postgresql+asyncpg", "postgresql"
        )
        while True:
            closed = asyncio.Event()
            connection: asyncpg.Connection | None = None
            try:
                connection = await asyncpg.connect(dsn)
                connection.add_termination_listener(
                    lambda _c, event=closed: event.set()
                )
                await connection.add_listener(CHANNEL, self._on_notify)
                self._ready.set()
                logger.info("Realtime listener connected")
                await closed.wait()
            except asyncio.CancelledError:
                if connection is not None:
                    with contextlib.suppress(Exception):
                        await connection.close()
                raise
            except Exception:
                logger.exception("Realtime listener failed, reconnecting")
            self._ready.clear()
            await asyncio.sleep(1)

    async def start(self) -> None:
        if self._listener is None:
            self._listener = asyncio.create_task(self._listen_forever())
            await asyncio.wait_for(self._ready.wait(), timeout=10)

    async def stop(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener
            self._listener = None


hub = Hub()
