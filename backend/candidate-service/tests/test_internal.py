from httpx import AsyncClient

from app.core.config import settings
from tests.conftest import User, published_profile

HEADERS = {"X-Internal-Token": settings.internal_api_token}


async def test_internal_api_requires_token(client: AsyncClient) -> None:
    assert (await client.get("/internal/v1/events")).status_code == 401


async def test_verified_grade_from_assessment(
    client: AsyncClient, candidate: User
) -> None:
    await published_profile(client, candidate)

    response = await client.put(
        f"/internal/v1/candidates/{candidate.id}/verified-grade",
        json={"grade": "senior", "assessment_id": "a-1"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["data"]["verified_grade"] == "senior"
    me = await client.get("/api/v1/candidates/me", headers=candidate.headers)
    assert me.json()["grade"] == "middle"
    assert me.json()["verified_grade"] == "senior"


async def test_event_feed_for_matching(client: AsyncClient, candidate: User) -> None:
    await published_profile(client, candidate)
    await client.patch(
        "/api/v1/candidates/me", json={"grade": "senior"}, headers=candidate.headers
    )

    events = (await client.get("/internal/v1/events", headers=HEADERS)).json()

    assert [e["event_type"] for e in events] == [
        "candidate.profile.published",
        "candidate.profile.updated",
    ]
    assert events[1]["payload"]["grade"] == "senior"
    assert "Python" in [s["name"] for s in events[1]["payload"]["skills"]]

    after = await client.get(
        "/internal/v1/events", params={"after_id": events[0]["id"]}, headers=HEADERS
    )
    assert len(after.json()) == 1


async def test_bulk_snapshots(client: AsyncClient, candidate: User) -> None:
    await published_profile(client, candidate)
    User("candidate")  # профиль без публикации не попадает в выгрузку

    response = await client.get("/internal/v1/candidates", headers=HEADERS)

    assert [c["user_id"] for c in response.json()] == [str(candidate.id)]
