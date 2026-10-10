"""Общие фикстуры тестов.

Тесты работают с настоящим PostgreSQL (по умолчанию auth-db из
docker-compose на localhost:5433) в отдельной базе ``<POSTGRES_DB>_test``.
"""

import os
import tempfile
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field

# Настройки читаются при импорте приложения — задаём окружение заранее.
os.environ["APP_ENV"] = "test"
os.environ["POSTGRES_DB"] = os.environ.get("POSTGRES_DB", "auth") + "_test"
os.environ["JWT_PRIVATE_KEY_PATH"] = os.path.join(tempfile.mkdtemp(), "jwt_private.pem")
os.environ["FSP_ID_ENABLED"] = "false"
os.environ["KEYCLOAK_ENABLED"] = "false"
os.environ["OUTBOX_RELAY_ENABLED"] = "false"

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.mail_client import get_mail_client  # noqa: E402


@dataclass
class FakeMailClient:
    # Последний код, отправленный на адрес, и его назначение.
    codes: dict[str, str] = field(default_factory=dict)
    purposes: dict[str, str] = field(default_factory=dict)
    # Информационные письма: (адрес, тема, текст).
    notifications: list[tuple[str, str, str]] = field(default_factory=list)
    fail: bool = False

    async def send_verification_code(
        self, *, to: str, code: str, ttl_minutes: int, purpose: str = "verify_email"
    ) -> None:
        from app.services.mail_client import MailDeliveryError

        if self.fail:
            raise MailDeliveryError("smtp down")
        self.codes[to] = code
        self.purposes[to] = purpose

    async def send_notification(self, *, to: str, subject: str, body: str) -> None:
        self.notifications.append((to, subject, body))


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
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture
def mail() -> Iterator[FakeMailClient]:
    fake = FakeMailClient()
    app.dependency_overrides[get_mail_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_mail_client, None)


@pytest.fixture
async def client(mail: FakeMailClient) -> AsyncIterator[AsyncClient]:
    """HTTP-клиент, отправляющий запросы напрямую в ASGI-приложение."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
