from typing import Any

from benefit_common.testing import TestUser
from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models import OutboxMessage
from tests.conftest import FakeEmployers

API = "/api/v1/applications"


def candidate_with_profile(candidates: Any) -> TestUser:
    user = TestUser("candidate")
    candidates.profiles[user.id] = {"status": "draft"}
    return user


async def outbox(kind: str) -> list[dict[str, Any]]:
    async with async_session_factory() as session:
        rows = await session.scalars(
            select(OutboxMessage)
            .where(OutboxMessage.kind == kind)
            .order_by(OutboxMessage.id)
        )
        return [r.payload for r in rows]


async def apply(client: AsyncClient, user: TestUser, vacancy_id: Any) -> Any:
    return await client.post(
        API,
        json={"vacancy_id": str(vacancy_id), "cover_letter": "Хочу к вам"},
        headers=user.headers,
    )


async def test_application_grants_contacts_and_opens_chat(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer = TestUser("employer")
    candidate = candidate_with_profile(candidates)
    vacancy = employers.vacancy_of(employer.id)

    response = await apply(client, candidate, vacancy)

    assert response.status_code == 201, response.text
    application = response.json()
    assert (application["status"], application["company_name"]) == (
        "new",
        "ООО Вакансия",
    )
    [grant] = await outbox("candidate.contact_grant")
    assert grant == {
        "candidate_id": str(candidate.id),
        "employer_id": str(employer.id),
        "source": "application",
        "source_id": application["id"],
    }
    [chat] = await outbox("chat.conversation")
    assert (chat["source"], chat["invitation_id"]) == ("application", application["id"])
    [notification] = await outbox("notification")
    assert notification["user_id"] == str(employer.id)

    duplicate = await apply(client, candidate, vacancy)
    assert duplicate.json()["error"]["code"] == "already_applied"


async def test_apply_validation(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer = TestUser("employer")
    draft = employers.vacancy_of(employer.id, status="draft")
    candidate = candidate_with_profile(candidates)
    assert (await apply(client, candidate, draft)).status_code == 404

    no_profile = TestUser("candidate")
    vacancy = employers.vacancy_of(employer.id)
    response = await apply(client, no_profile, vacancy)
    assert response.json()["error"]["code"] == "profile_required"
    assert (await apply(client, employer, vacancy)).status_code == 403


async def test_employer_works_with_applications(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer = TestUser("employer")
    vacancy = employers.vacancy_of(employer.id)
    first = (await apply(client, candidate_with_profile(candidates), vacancy)).json()
    second_candidate = candidate_with_profile(candidates)
    second = (await apply(client, second_candidate, vacancy)).json()

    received = await client.get(
        f"{API}/received", params={"vacancy_id": str(vacancy)}, headers=employer.headers
    )
    assert {a["id"] for a in received.json()} == {first["id"], second["id"]}
    other = TestUser("employer")
    assert (await client.get(f"{API}/received", headers=other.headers)).json() == []
    assert (
        await client.get(f"{API}/{first['id']}", headers=other.headers)
    ).status_code == 404

    viewed = await client.post(
        f"{API}/{first['id']}/status",
        json={"status": "viewed"},
        headers=employer.headers,
    )
    assert viewed.json()["status"] == "viewed"
    invited = await client.post(
        f"{API}/{first['id']}/status",
        json={"status": "invited", "message": "Ждём в среду в 11:00"},
        headers=employer.headers,
    )
    assert invited.json()["employer_message"] == "Ждём в среду в 11:00"
    back = await client.post(
        f"{API}/{first['id']}/status",
        json={"status": "viewed"},
        headers=employer.headers,
    )
    assert back.status_code == 409

    # Кандидат видит только свои отклики и может отозвать.
    mine = await client.get(API, headers=second_candidate.headers)
    assert [a["id"] for a in mine.json()] == [second["id"]]
    withdrawn = await client.post(
        f"{API}/{second['id']}/withdraw", headers=second_candidate.headers
    )
    assert withdrawn.json()["status"] == "withdrawn"
    chat_events = [c["invitation_status"] for c in await outbox("chat.conversation")]
    assert chat_events.count("withdrawn") == 1 and "invited" in chat_events


async def test_invitation_uses_company_profile_and_vacancy(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    employer = TestUser("employer")
    candidate = TestUser("candidate")
    candidates.profiles[candidate.id] = {"status": "published"}
    url = "/api/v1/invitations"

    response = await client.post(
        url,
        json={"candidate_id": str(candidate.id), "vacancy": {"title": "Тимлид"}},
        headers=employer.headers,
    )
    assert response.json()["error"]["code"] == "company_required"

    employers.companies[employer.id] = {"name": "ООО Профиль"}
    response = await client.post(
        url,
        json={
            "candidate_id": str(candidate.id),
            "vacancy": {"title": "Тимлид", "salary_from": 400000},
        },
        headers=employer.headers,
    )
    assert response.json()["vacancy"]["company_name"] == "ООО Профиль"

    vacancy = employers.vacancy_of(employer.id)
    response = await client.post(
        url,
        json={
            "candidate_id": str(candidate.id),
            "vacancy": {"vacancy_id": str(vacancy)},
        },
        headers=employer.headers,
    )
    body = response.json()["vacancy"]
    assert (body["title"], body["salary_to"], body["company_name"]) == (
        "Middle Python Developer",
        350000,
        "ООО Вакансия",
    )
    foreign = employers.vacancy_of(TestUser("employer").id)
    response = await client.post(
        url,
        json={
            "candidate_id": str(candidate.id),
            "vacancy": {"vacancy_id": str(foreign)},
        },
        headers=employer.headers,
    )
    assert response.status_code == 404


async def test_internal_contacts(
    client: AsyncClient, candidates: Any, employers: FakeEmployers
) -> None:
    from benefit_common.settings import get_common_settings

    employer = TestUser("employer")
    applicant = candidate_with_profile(candidates)
    await apply(client, applicant, employers.vacancy_of(employer.id))
    invited = TestUser("candidate")
    candidates.profiles[invited.id] = {"status": "published"}
    invitation = await client.post(
        "/api/v1/invitations",
        json={
            "candidate_id": str(invited.id),
            "vacancy": {"title": "QA", "company_name": "ООО"},
        },
        headers=employer.headers,
    )
    await client.post(
        f"/api/v1/invitations/{invitation.json()['id']}/decline",
        headers=invited.headers,
    )
    url = f"/internal/v1/employers/{employer.id}/contacts"
    headers = {"X-Internal-Token": get_common_settings().internal_api_token}

    contacts = (await client.get(url, headers=headers)).json()

    assert contacts == {
        str(applicant.id): "application:new",
        str(invited.id): "invitation:declined",
    }
    assert (await client.get(url)).status_code == 401
