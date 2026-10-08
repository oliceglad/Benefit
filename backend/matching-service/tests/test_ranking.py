"""Эталонные тесты качества подбора: порядок и обоснование на подобранных
профилях. Если меняете веса в scoring.py — эти тесты показывают, не
ухудшилась ли точность."""

from typing import Any

import pytest
from benefit_common.settings import get_common_settings
from benefit_common.testing import TestUser
from httpx import AsyncClient

from app.services.indexer import Indexer
from tests.conftest import FakeSource, document

INTERNAL = {"X-Internal-Token": get_common_settings().internal_api_token}

STACK = ("Python", "PostgreSQL", "Kafka", "Docker")
PAYMENTS = "Сервисы приёма платежей и биллинг под высокие нагрузки"


def job(start: str, end: str | None, technologies: tuple[str, ...], text: str) -> dict:
    return {
        "company": "ООО Пример",
        "position": "Backend-разработчик",
        "start_date": start,
        "end_date": end,
        "description": text,
        "technologies": list(technologies),
    }


PROFILES: dict[str, dict[str, Any]] = {
    "ideal": dict(
        grade_status="confirmed",
        percent=86,
        skills=STACK,
        levels={"Python": "advanced", "Kafka": "advanced"},
        jobs=[job("2021-01-01", None, STACK, PAYMENTS)],
        experience_months=68,
        fsp=1,
        fsp_level="federal",
        about=PAYMENTS,
    ),
    "strong_unconfirmed": dict(
        skills=STACK,
        jobs=[job("2021-01-01", None, STACK, PAYMENTS)],
        experience_months=68,
        about=PAYMENTS,
    ),
    "related_stack": dict(
        grade_status="confirmed",
        percent=80,
        skills=("Python", "PostgreSQL", "RabbitMQ", "Docker"),
        jobs=[
            job(
                "2022-01-01",
                None,
                ("Python", "PostgreSQL", "RabbitMQ"),
                "Интернет-магазин",
            )
        ],
        experience_months=50,
        about="Интернет-магазин и логистика",
    ),
    "listed_only": dict(
        skills=("Python", "PostgreSQL", "Kafka"), about="Учусь и пишу пет-проекты"
    ),
    "stale_stack": dict(
        skills=("Python", "PostgreSQL", "Kafka"),
        jobs=[
            job("2014-01-01", "2018-06-01", ("Python", "PostgreSQL", "Kafka"), PAYMENTS)
        ],
        experience_months=54,
        about=PAYMENTS,
    ),
    "expensive_senior": dict(
        grade="senior",
        skills=STACK,
        salary_from=500000,
        jobs=[job("2016-01-01", None, STACK, PAYMENTS)],
        experience_months=120,
    ),
    "weak_junior": dict(grade="junior", skills=("Python",), experience_months=6),
    "frontend": dict(roles=("frontend",), skills=("React", "TypeScript")),
}

NEED = {
    "specialization": "backend",
    "grade": "middle",
    "required_skills": ["Python", "PostgreSQL", "Kafka"],
    "optional_skills": ["Docker"],
    "title": "Python-разработчик в команду платежей",
    "team_description": "Разрабатываем сервисы приёма платежей и биллинга, "
    "микросервисная архитектура, высокие нагрузки",
    "industry": "fintech",
    "work_formats": ["remote"],
    "salary_to": 300000,
}


@pytest.fixture
async def people(source: FakeSource, indexer: Indexer) -> dict[str, str]:
    ids = {
        key: str(source.publish(document(name=f"{key} Кандидат", **params)))
        for key, params in PROFILES.items()
    }
    await indexer.sync_events()
    return ids


async def match(client: AsyncClient, **overrides: Any) -> dict[str, Any]:
    response = await client.post(
        "/internal/v1/match", json={**NEED, "limit": 50, **overrides}, headers=INTERNAL
    )
    assert response.status_code == 200, response.text
    return response.json()


def ranking(result: dict[str, Any], people: dict[str, str]) -> list[str]:
    names = {v: k for k, v in people.items()}
    return [names[c["candidate"]["user_id"]] for c in result["candidates"]]


def by_key(result: dict[str, Any], people: dict[str, str], key: str) -> dict[str, Any]:
    return next(
        c for c in result["candidates"] if c["candidate"]["user_id"] == people[key]
    )


async def test_ranking_order(client: AsyncClient, people: dict[str, str]) -> None:
    result = await match(client)
    order = ranking(result, people)

    assert order[0] == "ideal"
    # Стек, подтверждённый свежим опытом, весит больше записи в списке навыков.
    assert order.index("strong_unconfirmed") < order.index("listed_only")
    assert order.index("strong_unconfirmed") < order.index("stale_stack")
    assert "frontend" not in order
    assert "weak_junior" not in order  # слишком слабое соответствие
    assert result["excluded"]["insufficient_skills"] >= 1

    ideal = by_key(result, people, "ideal")
    assert ideal["fit"] == "excellent"
    assert ideal["matched_skills"] == ["Python", "PostgreSQL", "Kafka"]
    reasons = " | ".join(ideal["reasons"])
    assert "Опыт со стеком: Python — 5" in reasons
    assert "Опыт близок к задачам команды: платежей" in reasons
    assert "Грейд подтверждён тестированием (86%)" in reasons
    total = sum(part["points"] for part in ideal["breakdown"])
    assert abs(total - ideal["score"]) <= 1


async def test_explanations_for_partial_matches(
    client: AsyncClient, people: dict[str, str]
) -> None:
    result = await match(client)

    related = by_key(result, people, "related_stack")
    assert related["related_skills"] == [{"required": "Kafka", "has": "RabbitMQ"}]
    assert "Нет Kafka, но есть RabbitMQ (близкая технология)" in related["reasons"]
    stale = by_key(result, people, "stale_stack")
    assert any("давно не использовал" in r for r in stale["reasons"])
    senior = by_key(result, people, "expensive_senior")
    assert any("выше бюджета" in w for w in senior["warnings"])
    assert any("на ступень выше" in r for r in senior["reasons"])
    listed = by_key(result, people, "listed_only")
    assert any("не подтверждён" in w for w in listed["warnings"])

    hints = {(c["specialization"], c["grade"]): c["hint"] for c in result["categories"]}
    assert hints[("backend", "middle")].startswith("Точное совпадение")
    assert hints[("backend", "senior")].startswith("Грейд выше")


async def test_strict_filters_and_suggestions(
    client: AsyncClient, people: dict[str, str]
) -> None:
    result = await match(
        client, strict_skills=True, require_confirmed_grade=True, hard_budget=True
    )

    assert ranking(result, people) == ["ideal"]
    assert result["excluded"]["missing_required_skills"] >= 1
    assert result["excluded"]["unconfirmed_grade"] >= 1
    suggestions = {s["text"]: s["extra_candidates"] for s in result["suggestions"]}
    # Единственное препятствие у related_stack — отсутствие Kafka.
    assert suggestions["Сделайте навык «Kafka» желательным, а не обязательным"] == 1
    assert suggestions["Снимите требование подтверждённого грейда"] >= 2

    narrow = await match(client, grade_tolerance=0)
    assert "expensive_senior" not in ranking(narrow, people)
    experienced = await match(client, min_experience_months=60)
    assert set(ranking(experienced, people)) <= {
        "ideal",
        "strong_unconfirmed",
        "expensive_senior",
    }


async def test_feedback_personalizes_results(
    client: AsyncClient, people: dict[str, str]
) -> None:
    before = await match(client)
    liked = await match(client, liked_ids=[people["related_stack"]])

    related = by_key(liked, people, "related_stack")
    assert related["feedback"] == "like"
    assert any("Похож на отмеченных вами" in r for r in related["reasons"])
    assert related["score"] > by_key(before, people, "related_stack")["score"]

    disliked = await match(client, disliked_ids=[people["ideal"]])
    assert "ideal" not in ranking(disliked, people)
    assert disliked["excluded"]["disliked"] == 1
    # Похожие на отклонённого опускаются.
    assert (
        by_key(disliked, people, "strong_unconfirmed")["score"]
        < by_key(before, people, "strong_unconfirmed")["score"]
    )


async def test_contacted_candidates(
    client: AsyncClient, people: dict[str, str]
) -> None:
    result = await match(
        client,
        contacted={
            people["strong_unconfirmed"]: "invitation:declined",
            people["listed_only"]: "invitation:pending",
        },
    )

    assert "strong_unconfirmed" not in ranking(result, people)
    assert (
        by_key(result, people, "listed_only")["contact_status"] == "invitation:pending"
    )
    hidden = await match(
        client,
        contacted={people["listed_only"]: "application:new"},
        hide_contacted=True,
    )
    assert "listed_only" not in ranking(hidden, people)


async def test_similar_candidates(client: AsyncClient, people: dict[str, str]) -> None:
    employer = TestUser("employer")
    response = await client.get(
        f"/api/v1/talent/candidates/{people['ideal']}/similar", headers=employer.headers
    )

    similar = response.json()
    assert similar[0]["candidate"]["user_id"] == people["strong_unconfirmed"]
    assert set(similar[0]["shared_skills"]) == set(STACK)
    assert people["frontend"] not in [s["candidate"]["user_id"] for s in similar]


async def test_search_modes(client: AsyncClient, people: dict[str, str]) -> None:
    employer = TestUser("employer")

    async def search(**params: Any) -> list[str]:
        response = await client.get(
            "/api/v1/talent/candidates",
            params={"limit": 50, **params},
            headers=employer.headers,
        )
        names = {v: k for k, v in people.items()}
        return [names[i["user_id"]] for i in response.json()["items"]]

    any_mode = await search(skills=["Kafka", "RabbitMQ"], skills_mode="any")
    assert {"ideal", "related_stack"} <= set(any_mode)
    all_mode = await search(skills=["Kafka", "RabbitMQ"])
    assert all_mode == []
    seniors = await search(experience_min=8)
    assert seniors == ["expensive_senior"]
    budget = await search(salary_max=300000, specialization="backend")
    assert "expensive_senior" not in budget
    by_skills = await search(
        skills=["Python", "Kafka", "Docker"], skills_mode="any", sort="skills"
    )
    assert set(by_skills[:3]) == {"ideal", "strong_unconfirmed", "expensive_senior"}
