"""Фикстуры: PostgreSQL chat-db (localhost:5438), база ``*_test``."""

import os
import tempfile
import uuid
from collections.abc import AsyncIterator
from typing import Any

os.environ["APP_ENV"] = "test"
os.environ["BACKGROUND_JOBS_ENABLED"] = "false"
os.environ["POSTGRES_DB"] = os.environ.get("POSTGRES_DB", "chat") + "_test"
os.environ["FILES_DIR"] = tempfile.mkdtemp()

import pytest  # noqa: E402
from benefit_common.settings import get_common_settings  # noqa: E402
from benefit_common.testing import (  # noqa: E402
    TestUser,
    ensure_database,
    install_test_jwks,
)
from httpx import ASGITransport, AsyncClient  # noqa: E402
from httpx_ws.transport import ASGIWebSocketTransport  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import async_session_factory, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, OutboxMessage  # noqa: E402
from app.services.events import resolve_event  # noqa: E402
from app.services.realtime import hub  # noqa: E402

API = settings.api_prefix
INTERNAL = {"X-Internal-Token": get_common_settings().internal_api_token}


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
    # Realtime: настоящий LISTEN на тестовой базе.
    hub.resolver = resolve_event
    await hub.start()
    yield
    await hub.stop()
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
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


def ws_client() -> AsyncClient:
    """Клиент с поддержкой WebSocket. Создавать внутри теста: транспорт
    держит группу задач, которую нельзя закрыть из другой задачи."""
    return AsyncClient(
        transport=ASGIWebSocketTransport(app=app), base_url="http://test"
    )


@pytest.fixture
def candidate() -> TestUser:
    return TestUser("candidate", "dev@mail.ru")


@pytest.fixture
def employer() -> TestUser:
    return TestUser("employer", "hr@company.ru")


async def sync(
    client: AsyncClient,
    candidate: TestUser,
    employer: TestUser,
    status: str = "pending",
    invitation_id: uuid.UUID | None = None,
    event_key: str = "created",
) -> dict[str, Any]:
    response = await client.put(
        "/internal/v1/conversations",
        json={
            "invitation_id": str(invitation_id or uuid.UUID(int=1)),
            "candidate_id": str(candidate.id),
            "employer_id": str(employer.id),
            "vacancy_title": "Python-разработчик",
            "company_name": "ООО Ромашка",
            "invitation_status": status,
            "event_text": f"Приглашение: {status}",
            "event_key": event_key,
        },
        headers=INTERNAL,
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
async def conversation(
    client: AsyncClient, candidate: TestUser, employer: TestUser
) -> str:
    return (await sync(client, candidate, employer))["conversation_id"]


async def outbox(kind: str | None = None) -> list[dict[str, Any]]:
    async with async_session_factory() as session:
        query = select(OutboxMessage).order_by(OutboxMessage.id)
        if kind:
            query = query.where(OutboxMessage.kind == kind)
        return [m.payload for m in await session.scalars(query)]
