from datetime import UTC, datetime, timedelta
from typing import Any

from benefit_common.settings import get_common_settings
from benefit_common.testing import TestUser
from httpx import AsyncClient
from sqlalchemy import update

from app.db.session import async_session_factory
from app.models import Interview, JobOffer
from tests.conftest import FakeEmployers
from tests.test_applications import apply, candidate_with_profile, outbox
from tests.test_invitations import invite, published

API = "/api/v1/hiring"


def soon(days: int = 2) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


async def start_by_application(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> tuple[TestUser, TestUser, dict]:
    employer = TestUser("employer")
    candidate = candidate_with_profile(candidates)
    response = await apply(client, candidate, employers.vacancy_of(employer.id))
    assert response.status_code == 201, response.text
    [process] = (await client.get(f"{API}/processes", headers=employer.headers)).json()
    return employer, candidate, process


async def add_member(client: AsyncClient, employer: TestUser, name: str) -> dict:
    response = await client.post(
        f"{API}/team",
        json={"full_name": name, "position": "Тимлид", "email": "lead@company.ru"},
        headers=employer.headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def act(
    client: AsyncClient,
    user: TestUser,
    path: str,
    body: Any = None,
    method: str = "post",
) -> Any:
    return await client.request(method, f"{API}{path}", json=body, headers=user.headers)


async def test_application_starts_process(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer, candidate, process = await start_by_application(
        client, candidates, employers
    )

    assert (process["source"], process["stage"], process["status"]) == (
        "application",
        "new",
        "active",
    )
    assert process["candidate_id"] == str(candidate.id)
    [mine] = (await client.get(f"{API}/my", headers=candidate.headers)).json()
    assert mine["id"] == process["id"]
    assert [e["type"] for e in mine["history"]] == ["created"]


async def test_accepted_invitation_starts_process(
    client: AsyncClient, candidates: Any
) -> None:
    employer, accepted, declined = (
        TestUser("employer"),
        published(candidates),
        published(candidates),
    )
    for candidate, action in ((accepted, "accept"), (declined, "decline")):
        invitation = (await invite(client, employer, candidate)).json()
        await client.post(
            f"/api/v1/invitations/{invitation['id']}/{action}",
            headers=candidate.headers,
        )

    processes = (await client.get(f"{API}/processes", headers=employer.headers)).json()

    assert [(p["candidate_id"], p["source"]) for p in processes] == [
        (str(accepted.id), "invitation")
    ]


async def test_full_flow_until_hired(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer, candidate, process = await start_by_application(
        client, candidates, employers
    )
    pid = process["id"]
    recruiter = await add_member(client, employer, "Анна Рекрутер")
    lead = await add_member(client, employer, "Пётр Тимлид")

    detail = (
        await act(
            client,
            employer,
            f"/processes/{pid}/responsible",
            {"responsible_id": recruiter["id"]},
            "put",
        )
    ).json()
    assert detail["responsible"]["full_name"] == "Анна Рекрутер"

    response = await act(
        client,
        employer,
        f"/processes/{pid}/stage",
        {"stage": "screening", "comment": "Резюме подходит"},
    )
    assert response.json()["stage"] == "screening"

    response = await act(
        client,
        employer,
        f"/processes/{pid}/interviews",
        {
            "kind": "technical",
            "scheduled_at": soon(),
            "duration_minutes": 90,
            "format": "online",
            "location": "https://meet.example.ru/abc",
            "interviewer_ids": [lead["id"]],
        },
    )
    assert response.status_code == 201, response.text
    detail = response.json()
    assert detail["stage"] == "interview"  # этап сдвинулся автоматически
    [interview] = detail["interviews"]
    assert interview["interviewers"][0]["full_name"] == "Пётр Тимлид"

    # Итоги — после начала интервью.
    result = {"status": "completed", "rating": 5, "feedback": "Сильный кандидат"}
    path = f"/processes/{pid}/interviews/{interview['id']}/result"
    assert (await act(client, employer, path, result)).status_code == 409
    async with async_session_factory() as session:
        await session.execute(
            update(Interview).values(
                scheduled_at=datetime.now(UTC) - timedelta(hours=2)
            )
        )
        await session.commit()
    detail = (await act(client, employer, path, result)).json()
    assert detail["interviews"][0]["rating"] == 5

    await act(client, employer, f"/processes/{pid}/comments", {"text": "Берём!"})

    offer_body = {"salary": 320000, "start_date": None, "message": "Ждём вас"}
    response = await act(client, employer, f"/processes/{pid}/offers", offer_body)
    assert response.status_code == 201, response.text
    detail = response.json()
    assert detail["stage"] == "offer"
    [offer] = detail["offers"]
    assert (offer["status"], offer["position_title"]) == (
        "sent",
        "Middle Python Developer",
    )
    again = await act(client, employer, f"/processes/{pid}/offers", offer_body)
    assert again.json()["error"]["code"] == "offer_pending"

    # Кандидат не видит оценок, заметок и смены ответственного.
    mine = (await client.get(f"{API}/my/{pid}", headers=candidate.headers)).json()
    assert "rating" not in mine["interviews"][0]
    assert "feedback" not in mine["interviews"][0]
    types = [e["type"] for e in mine["history"]]
    assert "comment" not in types and "responsible_changed" not in types
    assert "interview_completed" not in types
    assert {"interview_scheduled", "offer_sent", "stage_changed"} <= set(types)

    accepted = await act(
        client,
        candidate,
        f"/my/{pid}/offers/{offer['id']}/accept",
        {"message": "Согласен"},
    )
    assert accepted.status_code == 200, accepted.text
    assert (accepted.json()["stage"], accepted.json()["status"]) == ("hired", "hired")

    detail = (await act(client, employer, f"/processes/{pid}", method="get")).json()
    assert detail["offers"][0]["status"] == "accepted"
    assert [e["type"] for e in detail["history"]][-3:] == [
        "offer_accepted",
        "stage_changed",
        "hired",
    ]
    # Завершённый процесс не меняется.
    stage = await act(client, employer, f"/processes/{pid}/stage", {"stage": "new"})
    assert stage.status_code == 409

    kinds = {(n["user_id"], n["type"]) for n in await outbox("notification")}
    assert (str(candidate.id), "hiring.interview_scheduled") in kinds
    assert (str(candidate.id), "hiring.offer_sent") in kinds
    assert (str(employer.id), "hiring.hired") in kinds


async def test_reject_closes_process_and_application(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer, candidate, process = await start_by_application(
        client, candidates, employers
    )
    pid = process["id"]
    await act(
        client, employer, f"/processes/{pid}/interviews", {"scheduled_at": soon()}
    )

    response = await act(
        client,
        employer,
        f"/processes/{pid}/reject",
        {"reason": "Мало опыта с Kafka", "message": "Спасибо за время"},
    )

    detail = response.json()
    assert (detail["status"], detail["rejection_reason"]) == (
        "rejected",
        "Мало опыта с Kafka",
    )
    assert detail["interviews"][0]["status"] == "cancelled"
    [application] = (
        await client.get("/api/v1/applications", headers=candidate.headers)
    ).json()
    assert application["status"] == "rejected"
    # Причина отказа — внутренняя, кандидат видит только сообщение.
    mine = (await client.get(f"{API}/my/{pid}", headers=candidate.headers)).json()
    assert "Мало опыта с Kafka" not in str(mine)
    assert "Спасибо за время" in str(mine)
    chat = (await outbox("chat.conversation"))[-1]
    assert chat["invitation_status"] == "rejected"  # переписка закрывается


async def test_candidate_withdraws(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer, candidate, process = await start_by_application(
        client, candidates, employers
    )

    response = await act(
        client, candidate, f"/my/{process['id']}/withdraw", {"message": "Нашёл работу"}
    )

    assert response.json()["status"] == "withdrawn"
    [application] = (
        await client.get("/api/v1/applications", headers=candidate.headers)
    ).json()
    assert application["status"] == "withdrawn"
    notes = [n for n in await outbox("notification") if n["type"] == "hiring.withdrawn"]
    assert notes[0]["user_id"] == str(employer.id)


async def test_application_status_is_reflected(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer, _, process = await start_by_application(client, candidates, employers)
    application_id = process["source_id"]

    await client.post(
        f"/api/v1/applications/{application_id}/status",
        json={"status": "invited"},
        headers=employer.headers,
    )
    detail = (
        await act(client, employer, f"/processes/{process['id']}", method="get")
    ).json()
    assert detail["stage"] == "interview"

    await client.post(
        f"/api/v1/applications/{application_id}/status",
        json={"status": "rejected", "message": "Не подходит"},
        headers=employer.headers,
    )
    detail = (
        await act(client, employer, f"/processes/{process['id']}", method="get")
    ).json()
    assert detail["status"] == "rejected"
    # Уведомление об отказе отправил сервис откликов — без дубля от найма.
    types = [n["type"] for n in await outbox("notification")]
    assert "hiring.rejected" not in types


async def test_offer_decline_and_expiry(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer, candidate, process = await start_by_application(
        client, candidates, employers
    )
    pid = process["id"]
    offer = (
        await act(client, employer, f"/processes/{pid}/offers", {"salary": 300000})
    ).json()["offers"][0]

    declined = await act(client, candidate, f"/my/{pid}/offers/{offer['id']}/decline")
    assert declined.json()["status"] == "active"
    assert declined.json()["offers"][0]["status"] == "declined"

    second = (
        await act(client, employer, f"/processes/{pid}/offers", {"salary": 350000})
    ).json()["offers"][-1]
    async with async_session_factory() as session:
        await session.execute(
            update(JobOffer)
            .where(JobOffer.id == second["id"])
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()

    mine = (await client.get(f"{API}/my/{pid}", headers=candidate.headers)).json()
    assert mine["offers"][-1]["status"] == "expired"
    late = await act(client, candidate, f"/my/{pid}/offers/{second['id']}/accept")
    assert late.json()["error"]["code"] == "offer_expired"


async def test_access_is_limited(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer, candidate, process = await start_by_application(
        client, candidates, employers
    )
    pid = process["id"]
    stranger, other_candidate = TestUser("employer"), TestUser("candidate")
    foreign = await add_member(client, stranger, "Чужой сотрудник")

    get = await act(client, stranger, f"/processes/{pid}", method="get")
    assert get.status_code == 404
    reject = await act(client, stranger, f"/processes/{pid}/reject", {})
    assert reject.status_code == 404
    mine = await client.get(f"{API}/my/{pid}", headers=other_candidate.headers)
    assert mine.status_code == 404
    # Кандидату недоступны действия работодателя.
    assert (
        await act(client, candidate, f"/processes/{pid}", method="get")
    ).status_code == 403
    # Сотрудника чужой компании нельзя назначить.
    response = await act(
        client,
        employer,
        f"/processes/{pid}/interviews",
        {"scheduled_at": soon(), "interviewer_ids": [foreign["id"]]},
    )
    assert response.json()["error"]["code"] == "team_member_not_found"
    team = (await client.get(f"{API}/team", headers=employer.headers)).json()
    assert team == []


async def test_validation_and_dictionaries(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer, _, process = await start_by_application(client, candidates, employers)
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()

    response = await act(
        client,
        employer,
        f"/processes/{process['id']}/interviews",
        {"scheduled_at": past},
    )
    assert response.status_code == 422
    hired = await act(
        client, employer, f"/processes/{process['id']}/stage", {"stage": "hired"}
    )
    assert hired.status_code == 422

    dictionaries = (await client.get(f"{API}/dictionaries")).json()
    assert {"id": "offer", "title": "Оффер"} in dictionaries["stages"]


async def test_account_deletion_removes_hiring_data(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer, candidate, process = await start_by_application(
        client, candidates, employers
    )
    await add_member(client, employer, "Анна Рекрутер")
    await act(
        client,
        employer,
        f"/processes/{process['id']}/interviews",
        {"scheduled_at": soon()},
    )
    internal = {"X-Internal-Token": get_common_settings().internal_api_token}

    for _ in range(2):  # идемпотентно
        response = await client.delete(
            f"/internal/v1/users/{candidate.id}", headers=internal
        )
        assert response.status_code == 204

    assert (await client.get(f"{API}/processes", headers=employer.headers)).json() == []
    applications = await client.get(
        "/api/v1/applications/received", headers=employer.headers
    )
    assert applications.json() == []

    await client.delete(f"/internal/v1/users/{employer.id}", headers=internal)
    assert (await client.get(f"{API}/team", headers=employer.headers)).json() == []
