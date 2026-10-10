"""Фикстуры: PostgreSQL employer-db (localhost:5439), база ``*_test``."""

import os
from collections.abc import AsyncIterator

os.environ["APP_ENV"] = "test"
os.environ["POSTGRES_DB"] = os.environ.get("POSTGRES_DB", "employers") + "_test"
os.environ["VERIFICATION_RECHECK_ENABLED"] = "false"

import pytest  # noqa: E402
from benefit_common.testing import ensure_database, install_test_jwks  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


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


COMPANY = {
    "name": "ООО Ромашка",
    "inn": "7707083893",
    "industry": "fintech",
    "description": "Делаем платёжные сервисы для малого бизнеса.",
    "website": "https://romashka.ru",
    "city": "Москва",
    "size": "51-200",
    "tech_stack": ["питон", "postgres", "Kafka"],
    "contact_name": "Анна HR",
    "contact_email": "hr@romashka.ru",
    "contact_phone": "+79990001122",
}

NEED = {
    "title": "Python-разработчик в команду платежей",
    "team_description": "Команда из 6 человек, сервисы приёма платежей.",
    "specialization": "backend",
    "grade": "middle",
    "required_skills": ["Python", "PostgreSQL"],
    "optional_skills": ["kafka"],
    "work_formats": ["remote"],
    "salary_from": 200000,
    "salary_to": 300000,
}

VACANCY = {
    "title": "Middle Python Developer",
    "description": "Разработка сервисов приёма платежей.",
    "specialization": "backend",
    "grade": "middle",
    "required_skills": ["Python", "FastAPI"],
    "optional_skills": ["Kafka"],
    "responsibilities": [
        "Разрабатывать сервисы приёма платежей",
        "Проводить код-ревью",
    ],
    "salary_from": 220000,
    "salary_type": "gross",
    "salary_to": 320000,
    "work_format": "remote",
    "employment_type": "full_time",
    "city": "Москва",
}
