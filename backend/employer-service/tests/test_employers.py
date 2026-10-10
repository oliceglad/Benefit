import uuid
from typing import Any

import pytest
from benefit_common.settings import get_common_settings
from benefit_common.testing import TestUser
from httpx import AsyncClient

from app.main import app
from app.services.matching import get_matcher
from tests.conftest import COMPANY, NEED, VACANCY

API = "/api/v1/employers"
INTERNAL = {"X-Internal-Token": get_common_settings().internal_api_token}


async def with_company(client: AsyncClient, employer: TestUser) -> dict:
    response = await client.put(
        f"{API}/company", json=COMPANY, headers=employer.headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_company_profile(client: AsyncClient) -> None:
    employer = TestUser("employer")
    assert (
        await client.get(f"{API}/company", headers=employer.headers)
    ).status_code == 404

    company = await with_company(client, employer)

    assert company["tech_stack"] == ["Python", "PostgreSQL", "Kafka"]
    updated = await client.put(
        f"{API}/company", json={**COMPANY, "city": "Казань"}, headers=employer.headers
    )
    assert updated.json()["id"] == company["id"]
    assert updated.json()["city"] == "Казань"
    candidate = TestUser("candidate")
    public = await client.get(
        f"{API}/companies/{company['id']}", headers=candidate.headers
    )
    assert public.json()["name"] == "ООО Ромашка"
    assert (
        await client.get(f"{API}/company", headers=candidate.headers)
    ).status_code == 403


@pytest.mark.parametrize("inn", ["1234567890", "123", "770708389X"])
async def test_invalid_inn(client: AsyncClient, inn: str) -> None:
    response = await client.put(
        f"{API}/company",
        json={**COMPANY, "inn": inn},
        headers=TestUser("employer").headers,
    )
    assert response.status_code == 422


async def test_needs_require_company_and_are_private(client: AsyncClient) -> None:
    employer = TestUser("employer")
    response = await client.post(f"{API}/needs", json=NEED, headers=employer.headers)
    assert response.json()["error"]["code"] == "company_required"

    await with_company(client, employer)
    need = (
        await client.post(f"{API}/needs", json=NEED, headers=employer.headers)
    ).json()
    assert need["optional_skills"] == ["Kafka"]
    assert need["status"] == "active"

    other = TestUser("employer")
    url = f"{API}/needs/{need['id']}"
    assert (await client.get(url, headers=other.headers)).status_code == 404
    closed = await client.patch(
        url, json={"status": "closed"}, headers=employer.headers
    )
    assert closed.json()["status"] == "closed"
    invalid = await client.post(
        f"{API}/needs",
        json={**NEED, "salary_from": 500000},
        headers=employer.headers,
    )
    assert invalid.status_code == 422


class FakeMatcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def match(self, criteria: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(criteria)
        return {
            "total": 1,
            "categories": [
                {"specialization": "backend", "grade": "middle", "count": 1}
            ],
            "candidates": [{"score": 87, "reasons": ["Стек: Python"]}],
            "excluded": {"low_score": 2},
            "suggestions": [],
            "keywords": ["платежей"],
        }


class FakeContacts:
    def __init__(self, contacts: dict[str, str]) -> None:
        self.data = contacts

    async def contacts(self, employer_id: Any) -> dict[str, str]:
        return self.data


async def test_matches_use_need_feedback_and_contacts(client: AsyncClient) -> None:
    from app.services.matching import get_contacts

    employer = TestUser("employer")
    await with_company(client, employer)
    need = (
        await client.post(
            f"{API}/needs",
            json={**NEED, "strict_skills": True, "grade_tolerance": 0},
            headers=employer.headers,
        )
    ).json()
    liked, disliked, invited = (str(uuid.uuid4()) for _ in range(3))
    url = f"{API}/needs/{need['id']}/feedback"
    await client.put(
        f"{url}/{liked}", json={"verdict": "like"}, headers=employer.headers
    )
    await client.put(
        f"{url}/{disliked}",
        json={"verdict": "dislike", "comment": "Нет опыта с платежами"},
        headers=employer.headers,
    )
    feedback = (await client.get(url, headers=employer.headers)).json()
    assert {f["verdict"] for f in feedback} == {"like", "dislike"}
    other = TestUser("employer")
    assert (
        await client.put(
            f"{url}/{liked}", json={"verdict": "like"}, headers=other.headers
        )
    ).status_code == 404

    matcher = FakeMatcher()
    app.dependency_overrides[get_matcher] = lambda: matcher
    app.dependency_overrides[get_contacts] = lambda: FakeContacts(
        {invited: "invitation:pending"}
    )
    try:
        response = await client.get(
            f"{API}/needs/{need['id']}/matches",
            params={"limit": 5, "hide_contacted": True},
            headers=employer.headers,
        )
    finally:
        app.dependency_overrides.pop(get_matcher, None)
        app.dependency_overrides.pop(get_contacts, None)

    assert response.status_code == 200, response.text
    assert response.json()["excluded"] == {"low_score": 2}
    [call] = matcher.calls
    assert call["required_skills"] == ["Python", "PostgreSQL"]
    assert call["industry"] == "fintech"  # отрасль компании
    assert call["team_description"].startswith("Команда из 6 человек")
    assert (call["strict_skills"], call["grade_tolerance"]) == (True, 0)
    assert call["liked_ids"] == [liked]
    assert call["disliked_ids"] == [disliked]
    assert call["contacted"] == {invited: "invitation:pending"}
    assert (call["limit"], call["hide_contacted"]) == (5, True)

    await client.delete(f"{url}/{liked}", headers=employer.headers)
    assert len((await client.get(url, headers=employer.headers)).json()) == 1


async def test_vacancy_lifecycle_and_catalog(client: AsyncClient) -> None:
    employer = TestUser("employer")
    candidate = TestUser("candidate")
    await with_company(client, employer)
    vacancy = (
        await client.post(f"{API}/vacancies", json=VACANCY, headers=employer.headers)
    ).json()
    assert vacancy["status"] == "draft"
    assert vacancy["company"]["name"] == "ООО Ромашка"

    catalog = "/api/v1/vacancies"
    assert (await client.get(catalog, headers=candidate.headers)).json()["total"] == 0
    assert (
        await client.get(f"{catalog}/{vacancy['id']}", headers=candidate.headers)
    ).status_code == 404

    published = await client.patch(
        f"{API}/vacancies/{vacancy['id']}",
        json={"status": "published"},
        headers=employer.headers,
    )
    assert published.json()["published_at"] is not None

    page = (
        await client.get(
            catalog,
            params={
                "specialization": "backend",
                "skill": "fastapi",
                "salary_min": 300000,
            },
            headers=candidate.headers,
        )
    ).json()
    assert [v["id"] for v in page["items"]] == [vacancy["id"]]
    none = await client.get(
        catalog, params={"grade": "senior"}, headers=candidate.headers
    )
    assert none.json()["total"] == 0

    edited = await client.put(
        f"{API}/vacancies/{vacancy['id']}",
        json={**VACANCY, "title": "Senior Python Developer"},
        headers=employer.headers,
    )
    assert edited.json()["title"] == "Senior Python Developer"
    other = TestUser("employer")
    response = await client.put(
        f"{API}/vacancies/{vacancy['id']}", json=VACANCY, headers=other.headers
    )
    assert response.status_code == 404


async def test_internal_api(client: AsyncClient) -> None:
    employer = TestUser("employer")
    company = await with_company(client, employer)
    vacancy = (
        await client.post(f"{API}/vacancies", json=VACANCY, headers=employer.headers)
    ).json()

    found = await client.get(
        f"/internal/v1/vacancies/{vacancy['id']}", headers=INTERNAL
    )
    assert found.json()["owner_id"] == str(employer.id)
    by_owner = await client.get(
        f"/internal/v1/companies/by-owner/{employer.id}", headers=INTERNAL
    )
    assert by_owner.json()["id"] == company["id"]
    assert (
        await client.get(f"/internal/v1/vacancies/{vacancy['id']}")
    ).status_code == 401


async def test_account_deletion_removes_company(client: AsyncClient) -> None:
    employer = TestUser("employer")
    await with_company(client, employer)
    vacancy = (
        await client.post(f"{API}/vacancies", json=VACANCY, headers=employer.headers)
    ).json()

    for _ in range(2):  # идемпотентно
        response = await client.delete(
            f"/internal/v1/users/{employer.id}", headers=INTERNAL
        )
        assert response.status_code == 204

    assert (
        await client.get(f"/internal/v1/vacancies/{vacancy['id']}", headers=INTERNAL)
    ).status_code == 404
    assert (
        await client.get(
            f"/internal/v1/companies/by-owner/{employer.id}", headers=INTERNAL
        )
    ).status_code == 404
