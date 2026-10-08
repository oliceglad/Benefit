"""Общие фикстуры тестов.

Нужен PostgreSQL candidate-db из docker-compose (localhost:5434); тесты
работают в отдельной базе ``<POSTGRES_DB>_test``. Токены подписываются
тестовым ключом, JWKS auth-service подменяется.
"""

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

os.environ["APP_ENV"] = "test"
os.environ["POSTGRES_DB"] = os.environ.get("POSTGRES_DB", "candidates") + "_test"

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from benefit_common.testing import TestUser, install_test_jwks  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.fsp import get_achievements_client, get_identity_client  # noqa: E402

User = TestUser


async def _ensure_database() -> None:
    conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", settings.postgres_db
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{settings.postgres_db}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def database() -> AsyncIterator[None]:
    await _ensure_database()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def jwks() -> None:
    install_test_jwks()


@pytest.fixture
def candidate() -> User:
    return User("candidate", "candidate@mail.ru")


@pytest.fixture
def employer() -> User:
    return User("employer", "hr@company.ru")


class FakeFsp:
    """Подменяет auth-service (привязка ФСП ID) и API достижений ФСП."""

    def __init__(self) -> None:
        self.linked: dict[uuid.UUID, str] = {}
        self.items: dict[str, list[dict[str, Any]]] = {}

    async def fsp_participant_id(self, user_id: uuid.UUID) -> str | None:
        return self.linked.get(user_id)

    async def achievements(self, participant_id: str) -> list[dict[str, Any]]:
        return self.items.get(participant_id, [])


@pytest.fixture
def fsp() -> Iterator[FakeFsp]:
    fake = FakeFsp()
    app.dependency_overrides[get_identity_client] = lambda: fake
    app.dependency_overrides[get_achievements_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_identity_client, None)
    app.dependency_overrides.pop(get_achievements_client, None)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


API = settings.api_prefix

FULL_PROFILE: dict[str, Any] = {
    "last_name": "Иванов",
    "first_name": "Иван",
    "middle_name": "Иванович",
    "birth_date": "1998-05-14",
    "city": "Казань",
    "relocation_ready": True,
    "phone": "8 (912) 345-67-89",
    "telegram": "https://t.me/ivanov_dev",
    "links": [{"type": "github", "url": "https://github.com/ivanov"}],
    "headline": "Python Backend-разработчик",
    "about": "Пишу надёжные сервисы на Python.\nЛюблю асинхронность.",
    "grade": "middle",
    "roles": ["backend"],
    "skills": [
        {"name": "питон", "level": "advanced", "years": 4},
        {"name": "FastAPI", "level": "advanced"},
        {"name": "postgres"},
        {"name": "Docker"},
    ],
    "soft_skills": ["Работа в команде", "Ответственность"],
    "languages": [
        {"language": "Русский", "level": "native"},
        {"language": "Английский", "level": "B2"},
    ],
    "experience": [
        {
            "company": "ООО Ромашка",
            "position": "Python-разработчик",
            "start_date": "2022-03-01",
            "end_date": None,
            "city": "Казань",
            "description": "Разработка микросервисов платёжной системы.",
            "achievements": ["Сократил время ответа API в 3 раза"],
            "technologies": ["Python", "FastAPI", "Kafka"],
        },
        {
            "company": "Яндекс",
            "position": "Стажёр-разработчик",
            "start_date": "2021-06-01",
            "end_date": "2022-02-01",
            "technologies": ["Python", "Django"],
        },
    ],
    "education": [
        {
            "institution": "Казанский федеральный университет",
            "level": "bachelor",
            "faculty": "Институт ВМиИТ",
            "specialization": "Прикладная информатика",
            "graduation_year": 2020,
        }
    ],
    "courses": [{"name": "Async Python", "organization": "Stepik", "year": 2023}],
    "salary_from": 250000,
    "employment_types": ["full_time"],
    "work_formats": ["remote", "hybrid"],
}


async def grant_consents(client: AsyncClient, user: User) -> None:
    statuses = (await client.get(f"{API}/me/consents", headers=user.headers)).json()
    for status in statuses:
        response = await client.post(
            f"{API}/me/consents",
            json={"type": status["type"], "version": status["required_version"]},
            headers=user.headers,
        )
        assert response.status_code == 200, response.text


async def published_profile(
    client: AsyncClient, user: User, **overrides: Any
) -> dict[str, Any]:
    response = await client.patch(
        f"{API}/me", json={**FULL_PROFILE, **overrides}, headers=user.headers
    )
    assert response.status_code == 200, response.text
    await grant_consents(client, user)
    response = await client.post(f"{API}/me/publish", headers=user.headers)
    assert response.status_code == 200, response.text
    return response.json()
