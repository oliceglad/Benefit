from typing import Any

import httpx
from benefit_common.settings import get_common_settings
from benefit_common.testing import TestUser
from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models import EmailDelivery
from app.services.delivery import EmailSender, build_relay

API = "/api/v1/notifications"
INTERNAL = {"X-Internal-Token": get_common_settings().internal_api_token}


async def notify(client: AsyncClient, user: TestUser, **extra: Any) -> httpx.Response:
    return await client.post(
        "/internal/v1/notifications",
        json={
            "user_id": str(user.id),
            "type": "invitation.received",
            "title": "Новое приглашение",
            "body": "ООО Ромашка приглашает на вакансию Python-разработчик",
            "link": "/invitations/42",
            **extra,
        },
        headers=INTERNAL,
    )


async def test_internal_api_requires_token(client: AsyncClient) -> None:
    response = await client.post("/internal/v1/notifications", json={})
    assert response.status_code == 401


async def test_user_sees_only_own_notifications(client: AsyncClient) -> None:
    alice, bob = TestUser("candidate"), TestUser("employer")
    assert (await notify(client, alice)).status_code == 201

    mine = (await client.get(API, headers=alice.headers)).json()
    others = (await client.get(API, headers=bob.headers)).json()

    assert mine["unread_count"] == 1
    assert mine["items"][0]["link"] == "/invitations/42"
    assert others == {"items": [], "unread_count": 0}


async def test_mark_read(client: AsyncClient) -> None:
    alice, bob = TestUser("candidate"), TestUser("candidate")
    created = (await notify(client, alice)).json()
    await notify(client, alice, dedup_key="second")

    url = f"{API}/{created['id']}/read"
    assert (await client.post(url, headers=bob.headers)).status_code == 404
    assert (await client.post(url, headers=alice.headers)).status_code == 204
    count = await client.get(f"{API}/unread-count", headers=alice.headers)
    assert count.json() == {"unread_count": 1}

    await client.post(f"{API}/read-all", headers=alice.headers)
    unread = await client.get(API, params={"unread_only": True}, headers=alice.headers)
    assert unread.json()["items"] == []


async def test_dedup_key_makes_creation_idempotent(client: AsyncClient) -> None:
    alice = TestUser("candidate")

    first = await notify(client, alice, dedup_key="invitation:42:created")
    second = await notify(client, alice, dedup_key="invitation:42:created")

    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    async with async_session_factory() as session:
        deliveries = (await session.scalars(select(EmailDelivery))).all()
    assert len(deliveries) == 1


class FakeService:
    def __init__(self, responses: dict[str, httpx.Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, Any]] = []

    async def get(self, path: str, **_: Any) -> httpx.Response:
        self.calls.append((path, None))
        return self._match(path)

    async def post(self, path: str, json: Any = None, **_: Any) -> httpx.Response:
        self.calls.append((path, json))
        return self._match(path)

    def _match(self, path: str) -> httpx.Response:
        for prefix, response in self.responses.items():
            if path.startswith(prefix):
                return response
        raise AssertionError(path)


def response(status: int, body: Any = None) -> httpx.Response:
    request = httpx.Request("GET", "http://test")
    return httpx.Response(status, json=body, request=request)


async def test_email_delivery_with_retry(client: AsyncClient) -> None:
    alice = TestUser("candidate")
    await notify(client, alice)
    auth = FakeService(
        {
            "/internal/v1/users/": response(
                200, {"email": "alice@mail.ru", "is_active": True}
            )
        }
    )

    # Первая попытка: почтовый сервис недоступен.
    class Unavailable(FakeService):
        async def post(self, path: str, json: Any = None, **_: Any) -> httpx.Response:
            raise RuntimeError("mail-service down")

    relay = build_relay(async_session_factory, EmailSender(auth, Unavailable({})))
    assert await relay.process_batch() == 1
    async with async_session_factory() as session:
        delivery = await session.scalar(select(EmailDelivery))
        assert delivery.sent_at is None
        assert delivery.attempts == 1
        delivery.next_attempt_at = delivery.created_at  # не ждём backoff
        await session.commit()

    mail = FakeService({"/api/v1/emails/": response(202, {"status": "sent"})})
    relay = build_relay(async_session_factory, EmailSender(auth, mail))
    assert await relay.process_batch() == 1

    path, payload = mail.calls[0]
    assert path == "/api/v1/emails/notification"
    assert payload["to"] == "alice@mail.ru"
    assert payload["action_url"] == "http://localhost:3000/invitations/42"
    async with async_session_factory() as session:
        delivery = await session.scalar(select(EmailDelivery))
        assert delivery.sent_at is not None


async def test_email_for_unknown_user_is_dropped(client: AsyncClient) -> None:
    await notify(client, TestUser("candidate"))
    auth = FakeService({"/internal/v1/users/": response(404)})
    relay = build_relay(async_session_factory, EmailSender(auth, FakeService({})))

    await relay.process_batch()

    async with async_session_factory() as session:
        delivery = await session.scalar(select(EmailDelivery))
        assert delivery.failed_at is not None
        assert delivery.attempts == 0


async def test_in_app_only_notification_has_no_email(client: AsyncClient) -> None:
    await notify(client, TestUser("candidate"), email=False)
    async with async_session_factory() as session:
        assert (await session.scalars(select(EmailDelivery))).all() == []


async def test_account_deletion_removes_notifications_and_emails(
    client: AsyncClient,
) -> None:
    alice, bob = TestUser("candidate"), TestUser("employer")
    await notify(client, alice)
    await notify(client, bob, dedup_key="bob-1")

    for _ in range(2):  # идемпотентно
        response = await client.delete(
            f"/internal/v1/users/{alice.id}", headers=INTERNAL
        )
        assert response.status_code == 204

    assert (await client.get(API, headers=alice.headers)).json()["items"] == []
    assert len((await client.get(API, headers=bob.headers)).json()["items"]) == 1
    async with async_session_factory() as session:
        queued = list(await session.scalars(select(EmailDelivery)))
    assert [e.payload["user_id"] for e in queued] == [str(bob.id)]
