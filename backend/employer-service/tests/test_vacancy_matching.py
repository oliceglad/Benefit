import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from benefit_common.testing import TestUser
from httpx import AsyncClient
from sqlalchemy import update

from app.db.session import async_session_factory
from app.main import app
from app.models import VacancyMatchSnapshot
from app.services.matching import get_contacts, get_matcher
from tests.conftest import COMPANY, NEED, VACANCY

API = "/api/v1/employers"

# Кандидаты «банка»: какие навыки у кого есть.
POOL = {
    str(uuid.uuid4()): {"python", "fastapi"},
    str(uuid.uuid4()): {"python", "fastapi", "postgresql"},
    str(uuid.uuid4()): {"python", "postgresql"},
}


class SkillMatcher:
    """Подбирает кандидатов, у которых есть все обязательные навыки."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def match(self, criteria: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(criteria)
        required = {s.lower() for s in criteria["required_skills"]}
        found = [
            {
                "score": 80,
                "contact_status": criteria["contacted"].get(user_id),
                "candidate": {"user_id": user_id},
            }
            for user_id, skills in POOL.items()
            if required <= skills and user_id not in criteria["disliked_ids"]
        ]
        return {
            "total": len(found),
            "categories": [],
            "candidates": found,
            "excluded": {},
            "suggestions": [],
            "keywords": [],
        }


class Contacts:
    def __init__(self) -> None:
        self.statuses: dict[str, str] = {}

    async def contacts(self, employer_id: uuid.UUID) -> dict[str, str]:
        return self.statuses


@pytest.fixture
def matcher() -> Iterator[SkillMatcher]:
    fake = SkillMatcher()
    app.dependency_overrides[get_matcher] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_matcher, None)


@pytest.fixture
def contacts() -> Iterator[Contacts]:
    fake = Contacts()
    app.dependency_overrides[get_contacts] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_contacts, None)


async def setup(client: AsyncClient, **vacancy: Any) -> tuple[TestUser, dict]:
    employer = TestUser("employer")
    await client.put(f"{API}/company", json=COMPANY, headers=employer.headers)
    response = await client.post(
        f"{API}/vacancies",
        json={**VACANCY, "optional_skills": [], **vacancy},
        headers=employer.headers,
    )
    assert response.status_code == 201, response.text
    return employer, response.json()


async def matches(
    client: AsyncClient, employer: TestUser, vacancy: dict, **params: Any
) -> dict:
    response = await client.get(
        f"{API}/vacancies/{vacancy['id']}/matches",
        params=params,
        headers=employer.headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def ids(result: dict) -> set[str]:
    return {c["candidate"]["user_id"] for c in result["candidates"]}


async def test_matching_uses_vacancy_requirements(
    client: AsyncClient, matcher: SkillMatcher, contacts: Contacts
) -> None:
    employer, vacancy = await setup(
        client, salary_to=300000, matching={"strict_skills": True}
    )

    result = await matches(client, employer, vacancy)

    assert result["recalculated"] == "initial"
    assert len(result["candidates"]) == 2  # Python + FastAPI
    [call] = matcher.calls
    assert call["required_skills"] == ["Python", "FastAPI"]
    assert call["work_formats"] == ["remote"]
    assert call["salary_to"] == 300000
    assert call["strict_skills"] is True
    # Обязанности участвуют в подборе как ключевые слова.
    assert "Проводить код-ревью" in call["team_description"]

    # Повторный запрос — из сохранённой подборки, без пересчёта.
    again = await matches(client, employer, vacancy)
    assert again["recalculated"] is None
    assert len(matcher.calls) == 1


async def test_changed_requirements_trigger_recalculation(
    client: AsyncClient, matcher: SkillMatcher, contacts: Contacts
) -> None:
    """Добавили PostgreSQL в обязательные навыки — подборка пересчитана,
    видно, кто выпал."""
    employer, vacancy = await setup(client)
    before = await matches(client, employer, vacancy)

    updated = await client.put(
        f"{API}/vacancies/{vacancy['id']}",
        json={
            **VACANCY,
            "optional_skills": [],
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        },
        headers=employer.headers,
    )
    state = updated.json()["matching_state"]
    assert (state["version"], state["computed_version"]) == (2, 1)
    assert state["requirements_changed"] is True

    after = await matches(client, employer, vacancy)

    assert after["recalculated"] == "criteria"
    assert after["matching_version"] == 2
    assert len(after["candidates"]) == 1
    changes = after["changes"]
    assert (changes["from_version"], changes["to_version"]) == (1, 2)
    assert set(changes["removed"]) == ids(before) - ids(after)
    assert changes["added"] == []
    vacancy_now = await client.get(
        f"{API}/vacancies/{vacancy['id']}", headers=employer.headers
    )
    assert vacancy_now.json()["matching_state"]["requirements_changed"] is False


async def test_grade_change_bumps_version_but_status_does_not(
    client: AsyncClient, matcher: SkillMatcher, contacts: Contacts
) -> None:
    employer, vacancy = await setup(client, grade="junior")
    await matches(client, employer, vacancy)

    published = await client.patch(
        f"{API}/vacancies/{vacancy['id']}",
        json={"status": "published"},
        headers=employer.headers,
    )
    # Смена статуса на подбор не влияет.
    assert published.json()["matching_state"]["version"] == 1

    regraded = await client.put(
        f"{API}/vacancies/{vacancy['id']}",
        json={**VACANCY, "optional_skills": [], "grade": "middle"},
        headers=employer.headers,
    )
    assert regraded.json()["matching_state"]["version"] == 2
    result = await matches(client, employer, vacancy)
    assert result["recalculated"] == "criteria"
    assert matcher.calls[-1]["grade"] == "middle"


async def test_feedback_ttl_and_refresh_rules(
    client: AsyncClient, matcher: SkillMatcher, contacts: Contacts
) -> None:
    employer, vacancy = await setup(client)
    first = await matches(client, employer, vacancy)
    disliked = sorted(ids(first))[0]

    await client.put(
        f"{API}/vacancies/{vacancy['id']}/feedback/{disliked}",
        json={"verdict": "dislike"},
        headers=employer.headers,
    )
    result = await matches(client, employer, vacancy)
    assert result["recalculated"] == "feedback"
    assert result["matching_version"] == 1  # требования не менялись
    assert disliked not in ids(result)

    forced = await matches(client, employer, vacancy, refresh=True)
    assert forced["recalculated"] == "refresh"

    async with async_session_factory() as session:
        await session.execute(
            update(VacancyMatchSnapshot).values(
                computed_at=datetime.now(UTC) - timedelta(hours=2)
            )
        )
        await session.commit()
    expired = await matches(client, employer, vacancy)
    assert expired["recalculated"] == "expired"


async def test_contacts_are_applied_without_recalculation(
    client: AsyncClient, matcher: SkillMatcher, contacts: Contacts
) -> None:
    employer, vacancy = await setup(client)
    first = await matches(client, employer, vacancy)
    invited, declined = sorted(ids(first))

    contacts.statuses = {invited: "invitation:pending", declined: "invitation:declined"}
    result = await matches(client, employer, vacancy)

    assert result["recalculated"] is None
    assert len(matcher.calls) == 1
    # Отказавшийся не показывается, приглашённый помечен.
    assert {
        c["candidate"]["user_id"]: c["contact_status"] for c in result["candidates"]
    } == {invited: "invitation:pending"}
    hidden = await matches(client, employer, vacancy, hide_contacted=True)
    assert hidden["candidates"] == []


async def test_vacancy_from_need_inherits_once(
    client: AsyncClient, matcher: SkillMatcher, contacts: Contacts
) -> None:
    employer = TestUser("employer")
    await client.put(f"{API}/company", json=COMPANY, headers=employer.headers)
    need = (
        await client.post(
            f"{API}/needs",
            json={**NEED, "strict_skills": True, "grade_tolerance": 0},
            headers=employer.headers,
        )
    ).json()
    liked = str(uuid.uuid4())
    await client.put(
        f"{API}/needs/{need['id']}/feedback/{liked}",
        json={"verdict": "like"},
        headers=employer.headers,
    )

    vacancy = (
        await client.post(
            f"{API}/vacancies",
            json={
                **VACANCY,
                "required_skills": [],
                "optional_skills": [],
                "need_id": need["id"],
            },
            headers=employer.headers,
        )
    ).json()

    assert vacancy["required_skills"] == NEED["required_skills"]
    assert (
        vacancy["matching"]["strict_skills"],
        vacancy["matching"]["grade_tolerance"],
    ) == (True, 0)
    feedback = await client.get(
        f"{API}/vacancies/{vacancy['id']}/feedback", headers=employer.headers
    )
    assert [f["candidate_id"] for f in feedback.json()] == [liked]

    # Дальше потребность и вакансия независимы.
    await client.put(
        f"{API}/needs/{need['id']}",
        json={**NEED, "required_skills": ["Go"]},
        headers=employer.headers,
    )
    unchanged = await client.get(
        f"{API}/vacancies/{vacancy['id']}", headers=employer.headers
    )
    assert unchanged.json()["required_skills"] == NEED["required_skills"]
    assert unchanged.json()["matching_state"]["version"] == 1


async def test_matching_access_and_archive(
    client: AsyncClient, matcher: SkillMatcher, contacts: Contacts
) -> None:
    employer, vacancy = await setup(client)
    stranger = TestUser("employer")
    response = await client.get(
        f"{API}/vacancies/{vacancy['id']}/matches", headers=stranger.headers
    )
    assert response.status_code == 404

    await client.patch(
        f"{API}/vacancies/{vacancy['id']}",
        json={"status": "archived"},
        headers=employer.headers,
    )
    archived = await client.get(
        f"{API}/vacancies/{vacancy['id']}/matches", headers=employer.headers
    )
    assert archived.json()["error"]["code"] == "vacancy_archived"
