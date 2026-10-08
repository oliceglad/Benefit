from typing import Any

import pytest
from benefit_common.testing import TestUser
from httpx import AsyncClient
from httpx_ws import WebSocketDisconnect, aconnect_ws
from httpx_ws._api import AsyncWebSocketSession

from tests.conftest import API, ws_client

WS = f"http://test{API}/ws"


async def auth(ws: AsyncWebSocketSession, user: TestUser) -> None:
    token = user.headers["Authorization"].removeprefix("Bearer ")
    await ws.send_json({"type": "auth", "token": token})
    ready = await ws.receive_json(timeout=5)
    assert ready == {"type": "ready", "user_id": str(user.id)}


async def receive(
    ws: AsyncWebSocketSession, event_type: str, message_id: str | None = None
) -> dict[str, Any]:
    """Следующее событие нужного типа (пинги и прочее пропускаются)."""
    while True:
        event = await ws.receive_json(timeout=5)
        if event["type"] != event_type:
            continue
        if message_id is None or event["message"]["id"] == message_id:
            return event


async def test_requires_auth_message() -> None:
    async with ws_client() as client, aconnect_ws(WS, client) as ws:
        await ws.send_json({"type": "auth", "token": "garbage"})
        with pytest.raises(WebSocketDisconnect) as exc:
            await ws.receive_json(timeout=5)
        assert exc.value.code == 4401


async def test_realtime_messages_between_parties(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    async with (
        ws_client() as wsc,
        aconnect_ws(WS, wsc) as candidate_ws,
        aconnect_ws(WS, wsc) as employer_ws,
    ):
        await auth(candidate_ws, candidate)
        await auth(employer_ws, employer)

        # Работодатель пишет через REST — кандидат получает событие по WS.
        await client.post(
            f"{API}/conversations/{conversation}/messages",
            json={"text": "Добрый день!"},
            headers=employer.headers,
        )
        event = await receive(candidate_ws, "message.created")
        assert event["message"]["text"] == "Добрый день!"
        assert event["message"]["sender_id"] == str(employer.id)

        # Кандидат отвечает через WS: подтверждение себе, событие собеседнику.
        await candidate_ws.send_json(
            {
                "type": "message.send",
                "conversation_id": conversation,
                "text": "Здравствуйте!",
                "client_id": "ws-1",
            }
        )
        ack = await receive(candidate_ws, "message.ack")
        assert ack["client_id"] == "ws-1"
        assert ack["message"]["text"] == "Здравствуйте!"
        # Собеседник получает то же сообщение (и своё — для других устройств).
        incoming = await receive(employer_ws, "message.created", ack["message"]["id"])
        assert incoming["message"]["sender_id"] == str(candidate.id)

        await candidate_ws.send_json(
            {"type": "typing", "conversation_id": conversation}
        )
        typing = await receive(employer_ws, "typing")
        assert typing["user_id"] == str(candidate.id)

        await employer_ws.send_json({"type": "read", "conversation_id": conversation})
        read = await receive(candidate_ws, "conversation.read")
        assert read["user_id"] == str(employer.id)


async def test_ws_errors_keep_connection(
    candidate: TestUser, conversation: str
) -> None:
    stranger = TestUser("candidate")
    async with ws_client() as wsc, aconnect_ws(WS, wsc) as ws:
        await auth(ws, stranger)
        await ws.send_json(
            {
                "type": "message.send",
                "conversation_id": conversation,
                "text": "Чужой диалог",
                "client_id": "x",
            }
        )
        error = await receive(ws, "error")
        assert (error["code"], error["client_id"]) == ("conversation_not_found", "x")

        await ws.send_json({"type": "ping"})
        assert (await receive(ws, "pong")) == {"type": "pong"}


async def test_events_only_for_participants(
    client: AsyncClient, employer: TestUser, conversation: str
) -> None:
    stranger = TestUser("candidate")
    async with ws_client() as wsc, aconnect_ws(WS, wsc) as ws:
        await auth(ws, stranger)
        await client.post(
            f"{API}/conversations/{conversation}/messages",
            json={"text": "Секрет"},
            headers=employer.headers,
        )
        await ws.send_json({"type": "ping"})
        # Первое, что получит посторонний, — ответ на пинг, а не сообщение.
        assert (await ws.receive_json(timeout=5))["type"] == "pong"
