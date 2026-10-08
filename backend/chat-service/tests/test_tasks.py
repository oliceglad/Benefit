from datetime import UTC, datetime, timedelta
from typing import Any

from benefit_common.testing import TestUser
from httpx import AsyncClient
from sqlalchemy import update

from app.db.session import async_session_factory
from app.models import Task
from app.services.chat import ChatService
from app.services.delivery import build_relay
from app.services.storage import get_storage
from app.services.tasks import TaskService
from tests.conftest import API, outbox, sync


def due(hours: float = 48) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


async def create_task(
    client: AsyncClient, employer: TestUser, conversation: str, **extra: Any
) -> Any:
    return await client.post(
        f"{API}/conversations/{conversation}/tasks",
        json={
            "title": "Спроектировать API",
            "description": "Опишите эндпоинты сервиса бронирования.",
            "due_at": due(),
            **extra,
        },
        headers=employer.headers,
    )


async def scheduler() -> dict[str, int]:
    async with async_session_factory() as session:
        return await TaskService(
            session, ChatService(session, get_storage())
        ).run_scheduled()


async def test_full_task_cycle(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    response = await create_task(client, employer, conversation)
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["status"] == "assigned"

    history = (
        await client.get(
            f"{API}/conversations/{conversation}/messages", headers=candidate.headers
        )
    ).json()
    assert history[-1]["kind"] == "task"
    assert history[-1]["task_id"] == task["id"]

    upload = await client.post(
        f"{API}/conversations/{conversation}/attachments",
        files={"file": ("api.md", b"# API\nGET /bookings", "text/markdown")},
        headers=candidate.headers,
    )
    submitted = await client.post(
        f"{API}/tasks/{task['id']}/submit",
        json={
            "response_type": "approach",
            "text": "REST + идемпотентные ключи для бронирования",
            "attachment_ids": [upload.json()["id"]],
        },
        headers=candidate.headers,
    )
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["response_type"] == "approach"

    reviewed = await client.post(
        f"{API}/tasks/{task['id']}/review",
        json={"result": "passed", "score": 90, "feedback": "Отличный подход"},
        headers=employer.headers,
    )
    assert reviewed.json()["status"] == "passed"
    assert reviewed.json()["score"] == 90

    activity = await outbox("candidate.activity")
    assert [a["kind"] for a in activity] == [
        "task_assigned",
        "task_submitted",
        "task_reviewed",
    ]
    assert activity[-1]["data"] == {"result": "passed", "score": 90}
    assert all(a["user_id"] == str(candidate.id) for a in activity)
    kinds = [n["type"] for n in await outbox("notification")]
    assert kinds == ["task.assigned", "task.submitted", "task.reviewed"]

    history = (
        await client.get(
            f"{API}/conversations/{conversation}/messages", headers=employer.headers
        )
    ).json()
    submission = next(m for m in history if m["kind"] == "task_submission")
    assert submission["attachments"][0]["filename"] == "api.md"
    assert "оценка 90/100" in history[-1]["text"]


async def test_roles_and_states(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    response = await client.post(
        f"{API}/conversations/{conversation}/tasks",
        json={"title": "X", "description": "Y", "due_at": due()},
        headers=candidate.headers,
    )
    assert response.status_code == 403
    assert (
        await create_task(client, employer, conversation, due_at=due(0.01))
    ).status_code == 422

    task = (await create_task(client, employer, conversation)).json()
    url = f"{API}/tasks/{task['id']}"
    review = await client.post(
        f"{url}/review", json={"result": "passed"}, headers=employer.headers
    )
    assert review.json()["error"]["code"] == "task_assigned"
    submit = {"response_type": "solution", "text": "Готово"}
    assert (
        await client.post(f"{url}/submit", json=submit, headers=candidate.headers)
    ).status_code == 200
    again = await client.post(f"{url}/submit", json=submit, headers=candidate.headers)
    assert again.json()["error"]["code"] == "task_submitted"

    stranger = TestUser("candidate")
    assert (await client.get(url, headers=stranger.headers)).status_code == 404
    mine = await client.get(f"{API}/tasks", headers=candidate.headers)
    assert [t["id"] for t in mine.json()] == [task["id"]]


async def test_scheduler_expires_and_reminds(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    soon = (await create_task(client, employer, conversation, due_at=due(5))).json()
    late = (await create_task(client, employer, conversation)).json()
    async with async_session_factory() as session:
        await session.execute(
            update(Task)
            .where(Task.id == late["id"])
            .values(due_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()

    counts = await scheduler()

    assert counts == {"expired": 1, "reminded": 1, "issued": 0}
    expired = await client.get(f"{API}/tasks/{late['id']}", headers=candidate.headers)
    assert expired.json()["status"] == "expired"
    response = await client.post(
        f"{API}/tasks/{late['id']}/submit",
        json={"response_type": "solution", "text": "Поздно"},
        headers=candidate.headers,
    )
    assert response.status_code == 409
    notifications = [n["type"] for n in await outbox("notification")]
    assert "task.reminder" in notifications and "task.expired" in notifications
    assert soon["status"] == "assigned"
    assert (await scheduler())["reminded"] == 0  # напоминание одно


async def test_recurring_task_is_reissued(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    first = (
        await create_task(client, employer, conversation, recurrence_days=7)
    ).json()
    assert first["next_issue_at"] is not None
    async with async_session_factory() as session:
        await session.execute(
            update(Task)
            .where(Task.id == first["id"])
            .values(next_issue_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()

    assert (await scheduler())["issued"] == 1

    tasks = (await client.get(f"{API}/tasks", headers=candidate.headers)).json()
    assert len(tasks) == 2
    second = tasks[0]
    assert second["series_id"] == first["id"]
    assert second["recurrence_days"] == 7
    stopped = await client.post(
        f"{API}/tasks/{second['id']}/stop-recurrence", headers=employer.headers
    )
    assert stopped.json()["next_issue_at"] is None


async def test_closing_conversation_cancels_tasks(
    client: AsyncClient, candidate: TestUser, employer: TestUser, conversation: str
) -> None:
    task = (await create_task(client, employer, conversation, recurrence_days=7)).json()

    await sync(client, candidate, employer, status="withdrawn", event_key="withdrawn")

    closed = (
        await client.get(f"{API}/tasks/{task['id']}", headers=employer.headers)
    ).json()
    assert closed["status"] == "cancelled"
    assert closed["next_issue_at"] is None


async def test_relay_delivers_activity_and_notifications(
    client: AsyncClient, employer: TestUser, conversation: str
) -> None:
    await create_task(client, employer, conversation)
    delivered: dict[str, list] = {"notification": [], "activity": []}

    async def to_notifications(payload: dict) -> None:
        delivered["notification"].append(payload)

    async def to_candidate(payload: dict) -> None:
        delivered["activity"].append(payload)

    relay = build_relay(async_session_factory, to_notifications, to_candidate)
    assert await relay.process_batch() == 2
    assert delivered["activity"][0]["kind"] == "task_assigned"
    assert delivered["notification"][0]["type"] == "task.assigned"
