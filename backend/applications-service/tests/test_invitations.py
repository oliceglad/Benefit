from datetime import UTC, datetime, timedelta
from typing import Any

from benefit_common.testing import TestUser
from httpx import AsyncClient
from sqlalchemy import select, update

from app.db.session import async_session_factory
from app.models import Invitation, OutboxMessage
from app.services.delivery import build_relay

API = "/api/v1/invitations"

VACANCY = {
    "title": "Python-разработчик",
    "company_name": "ООО Ромашка",
    "salary_from": 200000,
    "salary_to": 300000,
    "work_format": "remote",
}


def published(candidates: Any, status: str = "published") -> TestUser:
    user = TestUser("candidate")
    candidates.profiles[user.id] = {"status": status}
    return user


async def invite(
    client: AsyncClient, employer: TestUser, candidate: TestUser, **vacancy: Any
) -> Any:
    return await client.post(
        API,
        json={
            "candidate_id": str(candidate.id),
            "vacancy": {**VACANCY, **vacancy},
            "message": "Будем рады видеть вас в команде",
        },
        headers=employer.headers,
    )


async def outbox() -> list[dict]:
    async with async_session_factory() as session:
        rows = await session.scalars(select(OutboxMessage).order_by(OutboxMessage.id))
        return [{"kind": r.kind, "payload": r.payload} for r in rows]


async def notifications() -> list[dict]:
    return [m["payload"] for m in await outbox() if m["kind"] == "notification"]


async def test_invite_and_accept(client: AsyncClient, candidates: Any) -> None:
    employer, candidate = TestUser("employer"), published(candidates)

    response = await invite(client, employer, candidate)

    assert response.status_code == 201, response.text
    invitation = response.json()
    assert invitation["status"] == "pending"
    assert invitation["vacancy"]["salary_from"] == 200000
    [chat] = [m["payload"] for m in await outbox() if m["kind"] == "chat.conversation"]
    assert chat["invitation_status"] == "pending"
    assert chat["event_key"] == "created"
    assert "Будем рады" in chat["event_text"]
    [received] = await notifications()
    assert received["user_id"] == str(candidate.id)
    assert received["type"] == "invitation.received"
    assert "200 000 – 300 000 ₽" in received["body"]
    assert received["email"] is True

    incoming = await client.get(f"{API}/incoming", headers=candidate.headers)
    assert [i["id"] for i in incoming.json()] == [invitation["id"]]

    accepted = await client.post(
        f"{API}/{invitation['id']}/accept",
        json={"message": "Готов пообщаться"},
        headers=candidate.headers,
    )
    assert accepted.json()["status"] == "accepted"
    messages = await outbox()
    grant = next(m for m in messages if m["kind"] == "candidate.contact_grant")
    assert grant["payload"] == {
        "candidate_id": str(candidate.id),
        "employer_id": str(employer.id),
        "source": "invitation",
        "source_id": invitation["id"],
    }
    answer = (await notifications())[-1]
    assert answer["user_id"] == str(employer.id)
    assert answer["type"] == "invitation.accepted"
    assert "Готов пообщаться" in answer["body"]
    assert "Контакты кандидата" in answer["body"]
    assert answer["link"] == f"/candidates/{candidate.id}"

    again = await client.post(
        f"{API}/{invitation['id']}/decline", headers=candidate.headers
    )
    assert again.status_code == 409


async def test_decline_and_sent_list(client: AsyncClient, candidates: Any) -> None:
    employer, candidate = TestUser("employer"), published(candidates)
    invitation = (await invite(client, employer, candidate)).json()

    await client.post(f"{API}/{invitation['id']}/decline", headers=candidate.headers)

    sent = await client.get(
        f"{API}/sent", params={"status": "declined"}, headers=employer.headers
    )
    assert [i["status"] for i in sent.json()] == ["declined"]


async def test_access_is_limited_to_participants(
    client: AsyncClient, candidates: Any
) -> None:
    employer, candidate = TestUser("employer"), published(candidates)
    other_candidate, other_employer = published(candidates), TestUser("employer")
    invitation = (await invite(client, employer, candidate)).json()
    url = f"{API}/{invitation['id']}"

    assert (await client.get(url, headers=other_candidate.headers)).status_code == 404
    assert (await client.get(url, headers=other_employer.headers)).status_code == 404
    assert (
        await client.post(f"{url}/accept", headers=other_candidate.headers)
    ).status_code == 404
    assert (
        await client.get(f"{API}/incoming", headers=other_candidate.headers)
    ).json() == []
    # Работодатель не может принимать приглашения, кандидат — приглашать.
    assert (
        await client.post(f"{url}/accept", headers=employer.headers)
    ).status_code == 403
    assert (await invite(client, candidate, other_candidate)).status_code == 403
    assert (await client.get(url, headers=candidate.headers)).status_code == 200


async def test_only_published_candidates_can_be_invited(
    client: AsyncClient, candidates: Any
) -> None:
    employer = TestUser("employer")
    draft = published(candidates, status="draft")

    response = await invite(client, employer, draft)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "candidate_not_found"
    assert (await invite(client, employer, TestUser("candidate"))).status_code == 404


async def test_duplicate_and_validation(client: AsyncClient, candidates: Any) -> None:
    employer, candidate = TestUser("employer"), published(candidates)
    await invite(client, employer, candidate)

    duplicate = await invite(client, employer, candidate, title="python-РАЗРАБОТЧИК")
    assert duplicate.json()["error"]["code"] == "already_invited"
    other = await invite(client, employer, candidate, title="Тимлид")
    assert other.status_code == 201
    invalid = await invite(client, employer, candidate, salary_from=5, salary_to=1)
    assert invalid.status_code == 422


async def test_expired_invitation(client: AsyncClient, candidates: Any) -> None:
    employer, candidate = TestUser("employer"), published(candidates)
    invitation = (await invite(client, employer, candidate)).json()
    async with async_session_factory() as session:
        await session.execute(
            update(Invitation).values(expires_at=datetime.now(UTC) - timedelta(days=1))
        )
        await session.commit()

    response = await client.post(
        f"{API}/{invitation['id']}/accept", headers=candidate.headers
    )

    assert response.json()["error"]["code"] == "invitation_expired"
    incoming = await client.get(f"{API}/incoming", headers=candidate.headers)
    assert incoming.json()[0]["status"] == "expired"


async def test_withdraw(client: AsyncClient, candidates: Any) -> None:
    employer, candidate = TestUser("employer"), published(candidates)
    invitation = (await invite(client, employer, candidate)).json()

    response = await client.post(
        f"{API}/{invitation['id']}/withdraw", headers=employer.headers
    )

    assert response.json()["status"] == "withdrawn"
    assert (await notifications())[-1]["email"] is False


async def test_notifications_delivered_by_relay(
    client: AsyncClient, candidates: Any
) -> None:
    employer, candidate = TestUser("employer"), published(candidates)
    await invite(client, employer, candidate)
    sent: list[dict] = []

    async def publish(payload: dict) -> None:
        sent.append(payload)

    async def ignore(payload: dict) -> None:
        pass

    relay = build_relay(async_session_factory, publish, ignore, ignore)
    assert await relay.process_batch() == 2
    assert sent[0]["dedup_key"].startswith("invitation.received:")


async def test_declined_invitation_does_not_share_contacts(
    client: AsyncClient, candidates: Any
) -> None:
    employer, candidate = TestUser("employer"), published(candidates)
    invitation = (await invite(client, employer, candidate)).json()

    await client.post(f"{API}/{invitation['id']}/decline", headers=candidate.headers)

    kinds = {m["kind"] for m in await outbox()}
    assert "candidate.contact_grant" not in kinds
    chat = [m["payload"] for m in await outbox() if m["kind"] == "chat.conversation"]
    # Диалог закрывается: chat-service получает новый статус приглашения.
    assert [c["invitation_status"] for c in chat] == ["pending", "declined"]


async def test_contact_grant_delivered_by_relay(
    client: AsyncClient, candidates: Any
) -> None:
    employer, candidate = TestUser("employer"), published(candidates)
    invitation = (await invite(client, employer, candidate)).json()
    await client.post(f"{API}/{invitation['id']}/accept", headers=candidate.headers)
    grants: list[dict] = []

    async def notify(payload: dict) -> None:
        pass

    async def grant(payload: dict) -> None:
        grants.append(payload)

    await build_relay(async_session_factory, notify, grant, notify).process_batch()

    assert grants == [
        {
            "candidate_id": str(candidate.id),
            "employer_id": str(employer.id),
            "source": "invitation",
            "source_id": invitation["id"],
        }
    ]


async def test_invitation_links_company_profile(
    client: AsyncClient, candidates: Any, employers: Any
) -> None:
    """По company_id фронтенд показывает актуальный статус проверки компании."""
    employer, candidate = TestUser("employer"), published(candidates)
    company_id = "6f1c2b9e-1d2a-4c5b-9e8f-0a1b2c3d4e5f"
    employers.companies[employer.id] = {"id": company_id, "name": "ООО Ромашка"}

    invitation = (await invite(client, employer, candidate)).json()
    assert invitation["company_id"] == company_id

    employers.companies.clear()  # нет профиля компании — ссылки нет
    other = (await invite(client, employer, published(candidates))).json()
    assert other["company_id"] is None
