import copy
from datetime import UTC, datetime, timedelta
from typing import Any

from benefit_common.settings import get_common_settings
from benefit_common.testing import TestUser
from httpx import AsyncClient
from sqlalchemy import select, update

from app.db.session import async_session_factory
from app.models import OutboxMessage, TestAssignment
from tests.conftest import API, SURVEY, FakeChat, solve, start
from tests.fixtures import SAMPLE_PACK


def employer_test(**overrides: Any) -> dict[str, Any]:
    source = copy.deepcopy(SAMPLE_PACK["tests"][1])  # 10 задач
    for field in ("slug", "tasks_per_attempt"):
        source.pop(field)
    return {**source, "title": "Тест ООО Ромашка", **overrides}


def due(hours: float = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


async def outbox(kind: str) -> list[dict[str, Any]]:
    async with async_session_factory() as session:
        rows = await session.scalars(
            select(OutboxMessage)
            .where(OutboxMessage.kind == kind)
            .order_by(OutboxMessage.id)
        )
        return [r.payload for r in rows]


async def create(client: AsyncClient, employer: TestUser, **overrides: Any) -> dict:
    response = await client.post(
        f"{API}/employer/tests",
        json=employer_test(**overrides),
        headers=employer.headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def assign(
    client: AsyncClient, employer: TestUser, test_id: str, conversation_id: Any, **extra
) -> Any:
    return await client.post(
        f"{API}/employer/tests/{test_id}/assignments",
        json={"conversation_id": str(conversation_id), "due_at": due(), **extra},
        headers=employer.headers,
    )


async def test_employer_tests_are_private(
    client: AsyncClient, candidate: TestUser
) -> None:
    employer = TestUser("employer")
    test = await create(client, employer)
    assert test["tasks_per_attempt"] == 10  # по умолчанию — все задачи
    assert test["tasks"][0]["correct"]

    other = TestUser("employer")
    url = f"{API}/employer/tests/{test['id']}"
    assert (await client.get(url, headers=other.headers)).status_code == 404
    assert (await client.get(url, headers=candidate.headers)).status_code == 403
    assert [
        t["id"]
        for t in (
            await client.get(f"{API}/employer/tests", headers=employer.headers)
        ).json()
    ] == [test["id"]]

    # Ни в каталоге кандидатов, ни в админке тестов платформы.
    catalog = (await client.get(f"{API}/tests", headers=candidate.headers)).json()
    assert test["id"] not in [t["id"] for t in catalog]
    admin = TestUser("admin")
    admin_list = (await client.get(f"{API}/admin/tests", headers=admin.headers)).json()
    assert test["id"] not in [t["id"] for t in admin_list]


async def test_assign_validates_conversation(
    client: AsyncClient, candidate: TestUser, chat: FakeChat
) -> None:
    employer = TestUser("employer")
    test = await create(client, employer)
    foreign = chat.add(candidate, TestUser("employer"))
    closed = chat.add(candidate, employer, status="closed")
    open_ = chat.add(candidate, employer)

    assert (await assign(client, employer, test["id"], foreign)).status_code == 404
    response = await assign(client, employer, test["id"], closed)
    assert response.json()["error"]["code"] == "conversation_closed"
    response = await assign(client, employer, test["id"], open_, due_at=due(0.01))
    assert response.status_code == 422

    response = await assign(client, employer, test["id"], open_, message="Удачи!")
    assert response.status_code == 201
    assert response.json()["company_name"] == "ООО Ромашка"
    [card] = await outbox("chat.message")
    assert card["kind"] == "assessment"
    assert card["sender_id"] == str(employer.id)
    assert card["data"]["assignment_id"] == response.json()["id"]
    assert "Удачи!" in card["text"]
    [notification] = await outbox("notification")
    assert notification["user_id"] == str(candidate.id)
    assert notification["type"] == "employer_test.assigned"


async def test_candidate_passes_employer_test(
    client: AsyncClient, candidate: TestUser, chat: FakeChat
) -> None:
    employer = TestUser("employer")
    test = await create(client, employer)
    conversation = chat.add(candidate, employer)
    assignment = (await assign(client, employer, test["id"], conversation)).json()

    mine = (await client.get(f"{API}/assignments", headers=candidate.headers)).json()
    assert [a["id"] for a in mine] == [assignment["id"]]
    attempt = await client.post(
        f"{API}/assignments/{assignment['id']}/start", headers=candidate.headers
    )
    assert attempt.status_code == 200, attempt.text
    assert attempt.json()["total_tasks"] == 10

    final = await solve(client, candidate, attempt.json()["id"])

    result = final["attempt"]["result"]
    assert result["percent"] == 100
    # Грейд тестом работодателя не подтверждается.
    assert (result["outcome"], result["confirmed_grade"]) == (None, None)
    assert result["message"] == "Результат отправлен работодателю."
    assert await outbox("candidate.assessment") == []

    view = (
        await client.get(
            f"{API}/employer/assignments/{assignment['id']}", headers=employer.headers
        )
    ).json()
    assert view["status"] == "completed"
    assert view["result"]["percent"] == 100
    first = view["answers"][0]
    assert first["answer"] is not None and first["correct"]
    assert first["time_spent_seconds"] is not None

    chat_messages = await outbox("chat.message")
    assert "Кандидат прошёл тест" in chat_messages[-1]["text"]
    [activity] = await outbox("candidate.activity")
    assert activity["kind"] == "employer_test_completed"
    assert activity["data"]["percent"] == 100
    notifications = await outbox("notification")
    assert notifications[-1]["user_id"] == str(employer.id)

    # Тест работодателя не запускает кулдаун тестов платформы.
    await start(
        client,
        candidate,
        **{**SURVEY, "specialization": "qa_automation", "target_grade": "junior"},
    )


async def test_answers_hidden_while_in_progress(
    client: AsyncClient, candidate: TestUser, chat: FakeChat
) -> None:
    employer = TestUser("employer")
    test = await create(client, employer)
    assignment = (
        await assign(client, employer, test["id"], chat.add(candidate, employer))
    ).json()
    await client.post(
        f"{API}/assignments/{assignment['id']}/start", headers=candidate.headers
    )

    view = (
        await client.get(
            f"{API}/employer/assignments/{assignment['id']}", headers=employer.headers
        )
    ).json()
    assert view["status"] == "in_progress"
    assert view["answers"] == []
    again = await client.post(
        f"{API}/assignments/{assignment['id']}/start", headers=candidate.headers
    )
    assert again.json()["error"]["code"] == "assignment_in_progress"


async def test_decline_cancel_expire_and_access(
    client: AsyncClient, candidate: TestUser, chat: FakeChat
) -> None:
    employer = TestUser("employer")
    test = await create(client, employer)
    conversation = chat.add(candidate, employer)
    declined = (await assign(client, employer, test["id"], conversation)).json()
    cancelled = (await assign(client, employer, test["id"], conversation)).json()
    expired = (await assign(client, employer, test["id"], conversation)).json()

    stranger = TestUser("candidate")
    url = f"{API}/assignments/{declined['id']}"
    assert (await client.get(url, headers=stranger.headers)).status_code == 404

    response = await client.post(f"{url}/decline", headers=candidate.headers)
    assert response.json()["status"] == "declined"
    response = await client.post(
        f"{API}/employer/assignments/{cancelled['id']}/cancel", headers=employer.headers
    )
    assert response.json()["status"] == "cancelled"
    async with async_session_factory() as session:
        await session.execute(
            update(TestAssignment)
            .where(TestAssignment.id == expired["id"])
            .values(due_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()

    statuses = {
        a["id"]: a["status"]
        for a in (
            await client.get(f"{API}/assignments", headers=candidate.headers)
        ).json()
    }
    assert statuses[expired["id"]] == "expired"
    response = await client.post(
        f"{API}/assignments/{expired['id']}/start", headers=candidate.headers
    )
    assert response.json()["error"]["code"] == "assignment_expired"


async def test_archived_test_cannot_be_sent(
    client: AsyncClient, candidate: TestUser, chat: FakeChat
) -> None:
    employer = TestUser("employer")
    test = await create(client, employer)
    await client.patch(
        f"{API}/employer/tests/{test['id']}",
        json={"is_active": False},
        headers=employer.headers,
    )

    response = await assign(client, employer, test["id"], chat.add(candidate, employer))

    assert response.json()["error"]["code"] == "assessment_archived"


INTERNAL = {"X-Internal-Token": get_common_settings().internal_api_token}


async def delete_user(client: AsyncClient, user: TestUser) -> None:
    for _ in range(2):  # идемпотентно
        response = await client.delete(
            f"/internal/v1/users/{user.id}", headers=INTERNAL
        )
        assert response.status_code == 204, response.text


async def test_candidate_deletion_removes_attempts(
    client: AsyncClient, candidate: TestUser, chat: FakeChat
) -> None:
    employer = TestUser("employer")
    test = await create(client, employer)
    assignment = (
        await assign(client, employer, test["id"], chat.add(candidate, employer))
    ).json()
    attempt = await client.post(
        f"{API}/assignments/{assignment['id']}/start", headers=candidate.headers
    )
    await solve(client, candidate, attempt.json()["id"])
    await solve(client, candidate, (await start(client, candidate))["id"])

    await delete_user(client, candidate)

    history = await client.get(f"{API}/attempts", headers=candidate.headers)
    assert history.json() == []
    sent = await client.get(f"{API}/employer/assignments", headers=employer.headers)
    assert sent.json() == []
    # Тест работодателя остаётся.
    assert (
        len(
            (await client.get(f"{API}/employer/tests", headers=employer.headers)).json()
        )
        == 1
    )


async def test_employer_deletion_removes_own_tests(
    client: AsyncClient, candidate: TestUser, chat: FakeChat
) -> None:
    employer = TestUser("employer")
    test = await create(client, employer)
    assignment = (
        await assign(client, employer, test["id"], chat.add(candidate, employer))
    ).json()
    attempt = await client.post(
        f"{API}/assignments/{assignment['id']}/start", headers=candidate.headers
    )
    await solve(client, candidate, attempt.json()["id"])

    await delete_user(client, employer)

    tests = await client.get(f"{API}/employer/tests", headers=employer.headers)
    assert tests.json() == []
    mine = await client.get(f"{API}/assignments", headers=candidate.headers)
    assert mine.json() == []
