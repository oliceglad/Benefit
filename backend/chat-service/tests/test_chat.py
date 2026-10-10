import pytest
from benefit_common.testing import TestUser
from httpx import AsyncClient

from app.core.config import settings
from tests.conftest import API, outbox, sync


async def send(client: AsyncClient, user: TestUser, conversation: str, **body) -> dict:
    response = await client.post(
        f"{API}/conversations/{conversation}/messages", json=body, headers=user.headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def upload(
    client: AsyncClient,
    user: TestUser,
    conversation: str,
    name: str = "solution.py",
    data: bytes = b"print('hello')\n",
) -> tuple[int, dict]:
    response = await client.post(
        f"{API}/conversations/{conversation}/attachments",
        files={"file": (name, data, "application/octet-stream")},
        headers=user.headers,
    )
    return response.status_code, response.json()


async def test_conversation_created_from_invitation(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    again = await sync(client, candidate, employer)  # повторная доставка
    assert again["conversation_id"] == conversation

    for user in (candidate, employer):
        items = (await client.get(f"{API}/conversations", headers=user.headers)).json()
        assert [c["id"] for c in items] == [conversation]
    history = await client.get(
        f"{API}/conversations/{conversation}/messages", headers=candidate.headers
    )
    assert [(m["kind"], m["text"]) for m in history.json()] == [
        ("system", "Приглашение: pending")
    ]


async def test_strangers_have_no_access(client: AsyncClient, conversation: str) -> None:
    stranger = TestUser("candidate")
    url = f"{API}/conversations/{conversation}"
    assert (await client.get(url, headers=stranger.headers)).status_code == 404
    assert (
        await client.get(f"{url}/messages", headers=stranger.headers)
    ).status_code == 404
    response = await client.post(
        f"{url}/messages", json={"text": "Привет"}, headers=stranger.headers
    )
    assert response.status_code == 404
    assert (
        await client.get(f"{API}/conversations", headers=stranger.headers)
    ).json() == []


async def test_messages_unread_and_read(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    await send(client, employer, conversation, text="Здравствуйте! Удобно созвониться?")
    last = await send(client, employer, conversation, text="Завтра в 11:00?")

    view = (
        await client.get(
            f"{API}/conversations/{conversation}", headers=candidate.headers
        )
    ).json()
    assert view["unread_count"] == 3  # с системным сообщением о приглашении
    assert view["last_message"]["text"] == "Завтра в 11:00?"

    await client.post(
        f"{API}/conversations/{conversation}/read",
        json={"message_id": last["id"]},
        headers=candidate.headers,
    )
    view = (
        await client.get(
            f"{API}/conversations/{conversation}", headers=candidate.headers
        )
    ).json()
    assert view["unread_count"] == 0
    employer_view = (
        await client.get(
            f"{API}/conversations/{conversation}", headers=employer.headers
        )
    ).json()
    assert employer_view["other_party_last_read_at"] is not None


async def test_client_id_makes_send_idempotent(
    client: AsyncClient, candidate: TestUser, conversation: str
) -> None:
    first = await send(client, candidate, conversation, text="Да", client_id="c-1")
    second = await send(client, candidate, conversation, text="Да", client_id="c-1")

    assert first["id"] == second["id"]


async def test_pagination(
    client: AsyncClient, candidate: TestUser, conversation: str
) -> None:
    for i in range(5):
        await send(client, candidate, conversation, text=f"m{i}")
    url = f"{API}/conversations/{conversation}/messages"

    page = (
        await client.get(url, params={"limit": 2}, headers=candidate.headers)
    ).json()
    assert [m["text"] for m in page] == ["m3", "m4"]
    older = await client.get(
        url, params={"limit": 2, "before": page[0]["id"]}, headers=candidate.headers
    )
    assert [m["text"] for m in older.json()] == ["m1", "m2"]


async def test_closed_conversation_is_read_only(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    await sync(client, candidate, employer, status="declined", event_key="declined")
    # Опоздавшее событие не открывает закрытый диалог.
    await sync(client, candidate, employer, status="pending", event_key="late")

    view = (
        await client.get(
            f"{API}/conversations/{conversation}", headers=employer.headers
        )
    ).json()
    assert view["status"] == "closed"
    response = await client.post(
        f"{API}/conversations/{conversation}/messages",
        json={"text": "Ещё раз"},
        headers=employer.headers,
    )
    assert response.json()["error"]["code"] == "conversation_closed"


async def test_attachments(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    status, attachment = await upload(client, candidate, conversation)
    assert status == 201
    url = f"{API}/attachments/{attachment['id']}"
    # Пока файл не отправлен, его видит только загрузивший.
    assert (await client.get(url, headers=employer.headers)).status_code == 404

    message = await send(
        client, candidate, conversation, attachment_ids=[attachment["id"]]
    )
    assert message["attachments"][0]["filename"] == "solution.py"

    response = await client.get(url, headers=employer.headers)
    assert response.status_code == 200
    assert response.content == b"print('hello')\n"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["x-content-type-options"] == "nosniff"
    stranger = TestUser("employer")
    assert (await client.get(url, headers=stranger.headers)).status_code == 404

    # Уже отправленный файл повторно прикрепить нельзя.
    response = await client.post(
        f"{API}/conversations/{conversation}/messages",
        json={"attachment_ids": [attachment["id"]]},
        headers=candidate.headers,
    )
    assert response.json()["error"]["code"] == "invalid_attachments"


async def test_upload_restrictions(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    assert (await upload(client, candidate, conversation, "run.exe", b"MZ\x90"))[
        0
    ] == 415
    assert (await upload(client, candidate, conversation, "doc.pdf", b"MZ\x90"))[
        0
    ] == 415
    assert (await upload(client, candidate, conversation, "page.html", b"<script>"))[
        0
    ] == 415
    status, body = await upload(client, candidate, conversation, "../../etc/passwd.txt")
    assert (status, body["filename"]) == (201, "passwd.txt")

    _, other = await upload(client, employer, conversation)
    response = await client.post(
        f"{API}/conversations/{conversation}/messages",
        json={"attachment_ids": [other["id"]]},
        headers=candidate.headers,
    )
    assert response.status_code == 422


async def test_pending_uploads_are_limited(
    client: AsyncClient,
    candidate: TestUser,
    conversation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Неотправленные файлы не копятся без ограничений (защита диска)."""
    monkeypatch.setattr(settings, "max_pending_attachments", 2)
    first = (await upload(client, candidate, conversation))[1]
    assert (await upload(client, candidate, conversation))[0] == 201

    status, body = await upload(client, candidate, conversation)
    assert status == 429
    assert body["error"]["code"] == "too_many_pending_attachments"

    # Отправленный файл больше не считается неотправленным.
    await send(client, candidate, conversation, attachment_ids=[first["id"]])
    assert (await upload(client, candidate, conversation))[0] == 201


async def test_message_notifications_are_throttled(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    await send(client, employer, conversation, text="Первое")
    await send(client, employer, conversation, text="Второе")

    notifications = await outbox("notification")
    assert [n["user_id"] for n in notifications] == [str(candidate.id)] * 2
    # Одинаковый ключ: notification-service создаст одно уведомление и письмо.
    assert notifications[0]["dedup_key"] == notifications[1]["dedup_key"]
    assert notifications[0]["link"] == f"/chat/{conversation}"


async def test_internal_conversation_and_service_messages(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    from tests.conftest import INTERNAL

    info = await client.get(
        f"/internal/v1/conversations/{conversation}", headers=INTERNAL
    )
    assert info.json()["employer_id"] == str(employer.id)
    assert info.json()["status"] == "open"
    assert (
        await client.get(f"/internal/v1/conversations/{conversation}")
    ).status_code == 401

    body = {
        "kind": "assessment",
        "sender_id": str(employer.id),
        "text": "Тест «SQL»: 5 задач, 15 мин.",
        "data": {"assignment_id": "a-1"},
        "client_id": "assignment:a-1:assigned",
    }
    url = f"/internal/v1/conversations/{conversation}/messages"
    assert (await client.post(url, json=body, headers=INTERNAL)).status_code == 201
    assert (await client.post(url, json=body, headers=INTERNAL)).status_code == 201

    history = (
        await client.get(
            f"{API}/conversations/{conversation}/messages", headers=candidate.headers
        )
    ).json()
    cards = [m for m in history if m["kind"] == "assessment"]
    assert len(cards) == 1  # повторная доставка не дублирует
    assert cards[0]["data"] == {"assignment_id": "a-1"}
    assert cards[0]["sender_id"] == str(employer.id)

    stranger = {**body, "sender_id": str(TestUser("employer").id), "client_id": "x"}
    assert (await client.post(url, json=stranger, headers=INTERNAL)).status_code == 404


async def test_conversation_from_application(
    client: AsyncClient, candidate: TestUser, employer: TestUser
) -> None:
    import uuid

    from tests.conftest import INTERNAL

    payload = {
        "source": "application",
        "invitation_id": str(uuid.uuid4()),
        "candidate_id": str(candidate.id),
        "employer_id": str(employer.id),
        "vacancy_title": "Python-разработчик",
        "company_name": "ООО Ромашка",
        "invitation_status": "new",
        "event_text": "Кандидат откликнулся на вакансию",
        "event_key": "application:created",
    }
    created = await client.put(
        "/internal/v1/conversations", json=payload, headers=INTERNAL
    )
    conversation = created.json()["conversation_id"]
    view = (
        await client.get(
            f"{API}/conversations/{conversation}", headers=employer.headers
        )
    ).json()
    assert (view["source"], view["status"]) == ("application", "open")

    rejected = {
        **payload,
        "invitation_status": "rejected",
        "event_key": "application:rejected",
    }
    await client.put("/internal/v1/conversations", json=rejected, headers=INTERNAL)
    view = (
        await client.get(
            f"{API}/conversations/{conversation}", headers=employer.headers
        )
    ).json()
    assert view["status"] == "closed"
