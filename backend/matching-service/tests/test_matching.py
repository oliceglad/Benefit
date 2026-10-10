from benefit_common.settings import get_common_settings
from benefit_common.testing import TestUser
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db.session import async_session_factory
from app.models import CandidateIndex
from app.services.indexer import Indexer
from tests.conftest import FakeSource, document

API = "/api/v1/talent"
INTERNAL = {"X-Internal-Token": get_common_settings().internal_api_token}


async def indexed() -> int:
    async with async_session_factory() as session:
        return await session.scalar(select(func.count()).select_from(CandidateIndex))


async def test_index_follows_event_feed(source: FakeSource, indexer: Indexer) -> None:
    alice = source.publish(document(name="Петрова Анна"))
    source.publish(document(name="Иванов Иван"))
    source.event(alice)  # повтор события — без дублей

    assert await indexer.sync_events() == 3
    assert await indexed() == 2
    assert await indexer.sync_events() == 0  # курсор сохранён

    del source.documents[alice]  # профиль снят с публикации
    source.event(alice)
    await indexer.sync_events()
    assert await indexed() == 1


async def test_account_deletion_removes_candidate(
    client: AsyncClient, source: FakeSource, indexer: Indexer
) -> None:
    alice = source.publish(document(name="Петрова Анна"))
    source.publish(document(name="Иванов Иван"))
    await indexer.sync_events()

    for _ in range(2):  # идемпотентно
        response = await client.delete(f"/internal/v1/users/{alice}", headers=INTERNAL)
        assert response.status_code == 204

    assert await indexed() == 1


async def test_bootstrap_fills_empty_index(
    source: FakeSource, indexer: Indexer
) -> None:
    for _ in range(3):
        source.publish(document())
    source.feed.clear()
    assert await indexer.bootstrap() == 3
    assert await indexer.bootstrap() == 0  # индекс уже не пуст


async def search(client: AsyncClient, **params) -> dict:
    response = await client.get(
        f"{API}/candidates", params=params, headers=TestUser("employer").headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_search_filters(
    client: AsyncClient, source: FakeSource, indexer: Indexer
) -> None:
    source.publish(
        document(
            name="Бэкенд Подтверждённый", grade_status="confirmed", fsp=2, percent=82
        )
    )
    source.publish(document(name="Бэкенд Заявленный", skills=("Python", "Django")))
    source.publish(
        document(
            name="Фронтенд Сеньор",
            roles=("frontend",),
            grade="senior",
            skills=("React",),
            about="Интерфейсы",
        )
    )
    source.publish(document(name="Не Ищет", status="not_looking"))
    await indexer.sync_events()

    everyone = await search(client)
    assert everyone["total"] == 3  # «не ищу работу» по умолчанию скрыт
    # В карточках поиска контактов нет вовсе.
    assert all("phone" not in item for item in everyone["items"])
    backend = await search(client, specialization="backend")
    assert backend["total"] == 2
    confirmed = await search(client, grade_status="confirmed")
    assert [i["full_name"] for i in confirmed["items"]] == ["Бэкенд Подтверждённый"]
    django = await search(client, skills=["питон", "django"])
    assert [i["full_name"] for i in django["items"]] == ["Бэкенд Заявленный"]
    fsp = await search(client, has_fsp="true")
    assert fsp["items"][0]["fsp_count"] == 2
    seniors = await search(client, grade=["senior"])
    assert [i["full_name"] for i in seniors["items"]] == ["Фронтенд Сеньор"]
    # Полнотекстовый поиск с русской морфологией: «платёжный» ~ «платёжные».
    text = await search(client, q="платёжный сервис")
    assert text["total"] == 2
    categories = {
        (c["specialization"], c["grade"], c["grade_status"]): c["count"]
        for c in everyone["categories"]
    }
    assert categories[("backend", "middle", "not_confirmed")] == 1
    assert categories[("frontend", "senior", "not_confirmed")] == 1


async def test_search_is_for_employers(client: AsyncClient) -> None:
    candidate = TestUser("candidate")
    response = await client.get(f"{API}/candidates", headers=candidate.headers)
    assert response.status_code == 403


async def match(client: AsyncClient, **criteria) -> dict:
    body = {
        "specialization": "backend",
        "grade": "middle",
        "required_skills": ["Python", "PostgreSQL", "Kafka"],
        "optional_skills": ["Docker"],
        "industry": "fintech",
        "work_formats": ["remote"],
        "salary_to": 300000,
        **criteria,
    }
    response = await client.post("/internal/v1/match", json=body, headers=INTERNAL)
    assert response.status_code == 200, response.text
    return response.json()


async def test_match_scores_and_explains(
    client: AsyncClient, source: FakeSource, indexer: Indexer
) -> None:
    source.publish(
        document(
            name="Лучший Кандидат",
            grade_status="confirmed",
            percent=88,
            skills=("Python", "PostgreSQL", "Kafka", "Docker"),
            fsp=1,
        )
    )
    source.publish(document(name="Средний Кандидат", skills=("Python",)))
    source.publish(
        document(name="Дорогой Кандидат", salary_from=500000, days_inactive=200)
    )
    source.publish(
        document(name="Другой Профиль", roles=("designer",), skills=("Figma",))
    )
    await indexer.sync_events()

    result = await match(client)

    names = [c["candidate"]["full_name"] for c in result["candidates"]]
    assert names[0] == "Лучший Кандидат"
    assert "Другой Профиль" not in names
    best = result["candidates"][0]
    assert best["score"] >= 75
    assert best["fit"] in ("good", "excellent")
    reasons = " | ".join(best["reasons"])
    assert "Специализация: Backend-разработчик" in reasons
    assert "Грейд подтверждён тестированием (88%)" in reasons
    assert "Стек: Python, PostgreSQL, Kafka (3 из 3)" in reasons
    assert "Достижения ФСП: 1" in reasons
    expensive = next(
        c
        for c in result["candidates"]
        if c["candidate"]["full_name"] == "Дорогой Кандидат"
    )
    assert any("выше бюджета" in w for w in expensive["warnings"])
    assert any("Давно не обновлял" in w for w in expensive["warnings"])
    # Закрывает лишь 1 из 3 обязательных навыков — в подборку не попадает.
    assert "Средний Кандидат" not in names
    assert result["excluded"]["insufficient_skills"] == 1

    top = result["categories"][0]
    assert (top["specialization"], top["grade"], top["grade_status"]) == (
        "backend",
        "middle",
        "confirmed",
    )

    strict = await match(client, require_confirmed_grade=True)
    assert [c["candidate"]["full_name"] for c in strict["candidates"]] == [
        "Лучший Кандидат"
    ]


async def test_match_requires_internal_token(client: AsyncClient) -> None:
    response = await client.post("/internal/v1/match", json={})
    assert response.status_code == 401
