"""Фикстуры: PostgreSQL matching-db (localhost:5440), база ``*_test``."""

import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

os.environ["APP_ENV"] = "test"
os.environ["BACKGROUND_JOBS_ENABLED"] = "false"
os.environ["POSTGRES_DB"] = os.environ.get("POSTGRES_DB", "matching") + "_test"

import pytest  # noqa: E402
from benefit_common.testing import ensure_database, install_test_jwks  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import async_session_factory, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.indexer import Indexer  # noqa: E402


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
        await conn.execute(text(f"TRUNCATE {tables}"))


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


def document(
    *,
    name: str = "Иванов Иван",
    roles: tuple[str, ...] = ("backend",),
    grade: str = "middle",
    grade_status: str = "not_confirmed",
    skills: tuple[str, ...] = ("Python", "PostgreSQL"),
    fsp: int = 0,
    days_inactive: int = 1,
    salary_from: int | None = 250000,
    work_formats: tuple[str, ...] = ("remote",),
    industry: str | None = "fintech",
    city: str = "Москва",
    status: str = "active",
    about: str = "Разрабатываю платёжные сервисы",
    percent: float | None = None,
    levels: dict[str, str] | None = None,
    jobs: list[dict[str, Any]] | None = None,
    experience_months: int = 36,
    relocation_ready: bool = False,
    fsp_level: str | None = None,
) -> dict[str, Any]:
    """Поисковый документ в формате candidate-service."""
    last, first = name.split()
    return {
        "user_id": str(uuid.uuid4()),
        "last_name": last,
        "first_name": first,
        "middle_name": None,
        "city": city,
        "relocation_ready": relocation_ready,
        "headline": f"{roles[0]} developer",
        "about": about,
        "grade": grade,
        "industry": industry,
        "category": {
            "industry": industry,
            "specialization": roles[0],
            "grade": grade,
            "grade_status": grade_status,
            "test_title": "Python Backend — Middle" if percent else None,
            "percent": percent,
        },
        "roles": list(roles),
        "skills": [
            {"name": s, "level": (levels or {}).get(s), "years": None} for s in skills
        ],
        "experience": jobs or [{"position": "Разработчик", "description": about}],
        "total_experience_months": experience_months,
        "work_formats": list(work_formats),
        "employment_types": ["full_time"],
        "job_search_status": status,
        "salary_from": salary_from,
        "salary_currency": "RUB",
        "has_photo": False,
        "published_at": datetime.now(UTC).isoformat(),
        "phone": None,
        "contact_email": None,
        "actuality": {
            "status": "active",
            "last_active_at": (
                datetime.now(UTC) - timedelta(days=days_inactive)
            ).isoformat(),
            "tasks_passed": 1,
        },
        "fsp_achievements": [
            {
                "event": f"Чемпионат ФСП {i}",
                "place": 1,
                "result": "winner",
                "level": fsp_level,
            }
            for i in range(fsp)
        ],
    }


class FakeSource:
    """Подменяет candidate-service: документы и лента событий."""

    def __init__(self) -> None:
        self.documents: dict[uuid.UUID, dict[str, Any]] = {}
        self.feed: list[dict[str, Any]] = []

    def publish(self, doc: dict[str, Any]) -> uuid.UUID:
        user_id = uuid.UUID(doc["user_id"])
        self.documents[user_id] = doc
        self.event(user_id)
        return user_id

    def event(self, user_id: uuid.UUID) -> None:
        self.feed.append({"id": len(self.feed) + 1, "aggregate_id": str(user_id)})

    async def events(self, after_id: int, limit: int) -> list[dict[str, Any]]:
        return [e for e in self.feed if e["id"] > after_id][:limit]

    async def document(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        return self.documents.get(user_id)

    async def published_ids(self, offset: int, limit: int) -> list[uuid.UUID]:
        return list(self.documents)[offset : offset + limit]


@pytest.fixture
def source() -> FakeSource:
    return FakeSource()


@pytest.fixture
def indexer(source: FakeSource) -> Indexer:
    return Indexer(async_session_factory, source)
