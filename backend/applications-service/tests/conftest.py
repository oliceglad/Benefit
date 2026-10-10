"""Фикстуры: PostgreSQL applications-db (localhost:5437), база ``*_test``."""

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

os.environ["APP_ENV"] = "test"
os.environ["OUTBOX_RELAY_ENABLED"] = "false"
os.environ["POSTGRES_DB"] = os.environ.get("POSTGRES_DB", "applications") + "_test"

import pytest  # noqa: E402
from benefit_common.testing import ensure_database, install_test_jwks  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.candidates import get_candidate_directory  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def database() -> AsyncIterator[None]:
    await ensure_database(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    install_test_jwks()
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class FakeCandidates:
    """Подменяет candidate-service: профили кандидатов по id."""

    def __init__(self) -> None:
        self.profiles: dict[uuid.UUID, dict[str, Any]] = {}

    async def snapshot(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        return self.profiles.get(user_id)


@pytest.fixture
def candidates() -> Iterator[FakeCandidates]:
    fake = FakeCandidates()
    app.dependency_overrides[get_candidate_directory] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_candidate_directory, None)


class FakeEmployers:
    """Подменяет employer-service: компании и вакансии."""

    def __init__(self) -> None:
        self.companies: dict[uuid.UUID, dict[str, Any]] = {}
        self.vacancies: dict[uuid.UUID, dict[str, Any]] = {}

    def vacancy_of(
        self, employer_id: uuid.UUID, status: str = "published"
    ) -> uuid.UUID:
        vacancy_id = uuid.uuid4()
        self.vacancies[vacancy_id] = {
            "id": str(vacancy_id),
            "owner_id": str(employer_id),
            "status": status,
            "title": "Middle Python Developer",
            "company": {"id": str(uuid.uuid4()), "name": "ООО Вакансия"},
            "salary_from": 250000,
            "salary_to": 350000,
            "currency": "RUB",
            "work_format": "remote",
            "city": "Москва",
        }
        return vacancy_id

    async def company(self, owner_id: uuid.UUID) -> dict[str, Any] | None:
        return self.companies.get(owner_id)

    async def vacancy(self, vacancy_id: uuid.UUID) -> dict[str, Any] | None:
        return self.vacancies.get(vacancy_id)


@pytest.fixture(autouse=True)
def employers() -> Iterator[FakeEmployers]:
    from app.services.employers import get_employer_directory

    fake = FakeEmployers()
    app.dependency_overrides[get_employer_directory] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_employer_directory, None)
