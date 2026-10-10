from benefit_common.settings import get_common_settings
from httpx import AsyncClient
from sqlalchemy import TextClause, text

from app.db.session import engine
from tests.conftest import User, published_profile

HEADERS = {"X-Internal-Token": get_common_settings().internal_api_token}


async def test_internal_api_requires_token(client: AsyncClient) -> None:
    assert (await client.get("/internal/v1/events")).status_code == 401


async def push(client: AsyncClient, user: User, grade: str | None) -> None:
    response = await client.put(
        f"/internal/v1/candidates/{user.id}/assessment",
        json={
            "industry": "fintech",
            "specialization": "backend",
            "verified_grade": grade,
            "verified_at": "2026-10-08T10:00:00Z",
            "test_title": "Python Backend — Middle",
            "percent": 82.5,
        },
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text


async def category(client: AsyncClient, user: User, viewer: User) -> dict:
    url = f"/api/v1/candidates/{user.id}"
    return (await client.get(url, headers=viewer.headers)).json()["category"]


async def test_confirmed_grade_visible_to_employer(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate)  # заявлен middle

    await push(client, candidate, "middle")

    result = await category(client, candidate, employer)
    assert result["grade"] == "middle"
    assert result["grade_status"] == "confirmed"
    assert result["industry"] == "fintech"
    assert result["percent"] == 82.5


async def test_higher_verified_grade_shown(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate)

    await push(client, candidate, "senior")

    result = await category(client, candidate, employer)
    assert (result["grade"], result["grade_status"]) == ("senior", "confirmed")


async def test_lower_verified_grade_is_hidden(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate)

    await push(client, candidate, "junior")

    public = (
        await client.get(f"/api/v1/candidates/{candidate.id}", headers=employer.headers)
    ).json()
    assert (public["category"]["grade"], public["category"]["grade_status"]) == (
        "middle",
        "not_confirmed",
    )
    assert "junior" not in str(public)
    # Владелец видит свой фактический результат.
    me = (await client.get("/api/v1/candidates/me", headers=candidate.headers)).json()
    assert me["verified_grade"] == "junior"


async def test_unconfirmed_without_results(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate)
    await push(client, candidate, "middle")

    await push(client, candidate, None)  # срок действия подтверждения истёк

    result = await category(client, candidate, employer)
    assert (result["grade"], result["grade_status"]) == ("middle", "not_confirmed")


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


async def grant(client: AsyncClient, candidate: User, employer: User) -> int:
    response = await client.put(
        f"/internal/v1/candidates/{candidate.id}/contact-grants",
        json={
            "employer_id": str(employer.id),
            "source": "invitation",
            "source_id": "11111111-1111-1111-1111-111111111111",
        },
        headers=HEADERS,
    )
    return response.status_code


async def test_accepted_invitation_reveals_contacts(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate)
    other_employer = User("employer")
    url = f"/api/v1/candidates/{candidate.id}"

    hidden = (await client.get(url, headers=employer.headers)).json()
    assert (hidden["contact_access"], hidden["phone"]) == ("hidden", None)

    assert await grant(client, candidate, employer) == 204
    assert await grant(client, candidate, employer) == 204  # идемпотентно

    shown = (await client.get(url, headers=employer.headers)).json()
    assert shown["contact_access"] == "granted"
    assert shown["phone"] == "+79123456789"
    assert shown["telegram"] == "@ivanov_dev"
    # Другие работодатели контакты по-прежнему не видят.
    other = (await client.get(url, headers=other_employer.headers)).json()
    assert other["phone"] is None


async def test_grant_keeps_access_after_unpublish(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate)
    await grant(client, candidate, employer)
    await client.post("/api/v1/candidates/me/unpublish", headers=candidate.headers)
    url = f"/api/v1/candidates/{candidate.id}"

    assert (await client.get(url, headers=employer.headers)).status_code == 200
    stranger = User("employer")
    assert (await client.get(url, headers=stranger.headers)).status_code == 404


async def test_grant_for_missing_profile(client: AsyncClient, employer: User) -> None:
    assert await grant(client, User("candidate"), employer) == 404


async def activity(
    client: AsyncClient, user: User, kind: str, ref: str, days_ago: int = 0, **data
) -> int:
    from datetime import UTC, datetime, timedelta

    response = await client.put(
        f"/internal/v1/candidates/{user.id}/activities",
        json={
            "kind": kind,
            "ref_id": ref,
            "occurred_at": (datetime.now(UTC) - timedelta(days=days_ago)).isoformat(),
            "data": data,
        },
        headers=HEADERS,
    )
    return response.status_code


async def test_task_activity_builds_actuality(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate)
    for kind, ref, extra in [
        ("task_assigned", "t1", {}),
        ("task_submitted", "t1", {}),
        ("task_reviewed", "t1", {"result": "passed", "score": 90}),
        ("task_assigned", "t2", {}),
        ("task_expired", "t2", {}),
    ]:
        assert await activity(client, candidate, kind, ref, **extra) == 204
    # Повторная доставка не задваивает счётчики.
    assert await activity(client, candidate, "task_submitted", "t1") == 204

    public = (
        await client.get(f"/api/v1/candidates/{candidate.id}", headers=employer.headers)
    ).json()["actuality"]
    assert public["status"] == "active"
    assert (
        public["tasks_assigned"],
        public["tasks_submitted"],
        public["tasks_passed"],
        public["tasks_expired"],
    ) == (2, 1, 1, 1)
    events = (await client.get("/internal/v1/events", headers=HEADERS)).json()
    recorded = [e for e in events if e["event_type"] == "candidate.activity.recorded"]
    assert len(recorded) == 5

    await activity(client, candidate, "employer_test_completed", "a1", percent=80)
    public = (
        await client.get(f"/api/v1/candidates/{candidate.id}", headers=employer.headers)
    ).json()["actuality"]
    assert public["employer_tests_completed"] == 1


async def test_actuality_status_by_age(client: AsyncClient, candidate: User) -> None:
    from sqlalchemy import update

    from app.db.session import async_session_factory
    from app.models import CandidateProfile

    await published_profile(client, candidate)
    async with async_session_factory() as session:
        # Профиль давно не обновлялся.
        await session.execute(
            update(CandidateProfile)
            .where(CandidateProfile.user_id == candidate.id)
            .values(updated_at=CandidateProfile.updated_at - text_interval(120))
        )
        await session.commit()
    me = (await client.get("/api/v1/candidates/me", headers=candidate.headers)).json()
    assert me["actuality"]["status"] == "stale"

    # Решение задания освежает профиль.
    await activity(client, candidate, "task_submitted", "t9")
    me = (await client.get("/api/v1/candidates/me", headers=candidate.headers)).json()
    assert me["actuality"]["status"] == "active"


def text_interval(days: int) -> TextClause:
    return text(f"interval '{days} days'")


async def test_activity_for_missing_profile(client: AsyncClient) -> None:
    assert await activity(client, User("candidate"), "task_assigned", "t1") == 404


async def test_search_document_is_privacy_safe(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate, privacy={"show_salary": False})
    await grant(client, candidate, employer)  # доступ у работодателя не влияет
    url = f"/internal/v1/candidates/{candidate.id}/search-document"

    document = (await client.get(url, headers=HEADERS)).json()

    assert document["contact_access"] == "hidden"
    assert (document["phone"], document["contact_email"]) == (None, None)
    assert document["salary_from"] is None
    assert document["category"]["grade"] == "middle"
    await client.post("/api/v1/candidates/me/unpublish", headers=candidate.headers)
    assert (await client.get(url, headers=HEADERS)).status_code == 404


async def test_revoked_personal_data_consent_hides_profile(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate)
    await grant(client, candidate, employer)

    await client.delete(
        "/api/v1/candidates/me/consents/personal_data", headers=candidate.headers
    )

    response = await client.get(
        f"/api/v1/candidates/{candidate.id}", headers=employer.headers
    )
    assert response.status_code == 404


async def test_account_deletion_removes_candidate_data(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate)
    assert await grant(client, candidate, employer) == 204

    for _ in range(2):  # повторная доставка ничего не ломает
        response = await client.delete(
            f"/internal/v1/users/{candidate.id}", headers=HEADERS
        )
        assert response.status_code == 204
    view = await client.get(
        f"/api/v1/candidates/{candidate.id}", headers=employer.headers
    )
    assert view.status_code == 404
    events = (await client.get("/internal/v1/events", headers=HEADERS)).json()
    assert events[-1]["event_type"] == "candidate.profile.deleted"


async def test_employer_deletion_removes_contact_access(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate)
    await grant(client, candidate, employer)

    await client.delete(f"/internal/v1/users/{employer.id}", headers=HEADERS)

    async with engine.begin() as conn:
        grants = await conn.scalar(text("SELECT count(*) FROM contact_grants"))
    assert grants == 0
