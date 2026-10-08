"""Фикстуры: PostgreSQL assessment-db (localhost:5435), база ``*_test``."""

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

os.environ["APP_ENV"] = "test"
os.environ["OUTBOX_RELAY_ENABLED"] = "false"
os.environ["POSTGRES_DB"] = os.environ.get("POSTGRES_DB", "assessments") + "_test"

import pytest  # noqa: E402
from benefit_common.testing import (  # noqa: E402
    TestUser,
    ensure_database,
    install_test_jwks,
)
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import async_session_factory, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AssessmentTask, AttemptTask, Base  # noqa: E402
from app.schemas.content import TestPack  # noqa: E402
from app.services.candidates import get_candidate_directory  # noqa: E402
from app.services.content import ContentService  # noqa: E402
from tests.fixtures import SAMPLE_PACK  # noqa: E402

API = settings.api_prefix


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
    async with async_session_factory() as session:
        await ContentService(session).import_pack(
            TestPack.model_validate(SAMPLE_PACK), None, skip_existing=False
        )
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    install_test_jwks()
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE attempt_tasks, attempts, outbox_messages RESTART IDENTITY")
        )


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


@pytest.fixture
def candidate(candidates: FakeCandidates) -> TestUser:
    user = TestUser("candidate", "dev@mail.ru")
    candidates.profiles[user.id] = {
        "grade": "middle",
        "roles": ["backend"],
        "industry": "fintech",
        "skills": [{"name": "Python"}, {"name": "PostgreSQL"}],
        "total_experience_months": 42,
    }
    return user


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


SURVEY = {
    "industry": "fintech",
    "specialization": "backend",
    "target_grade": "middle",
    "years_of_experience": 3.5,
    "skills": ["Python", "FastAPI"],
}


async def correct_answer(attempt_task_id: str) -> Any:
    async with async_session_factory() as session:
        task = await session.scalar(
            select(AssessmentTask)
            .join(AttemptTask, AttemptTask.task_id == AssessmentTask.id)
            .where(AttemptTask.id == uuid.UUID(attempt_task_id))
        )
        assert task is not None
        return task.correct[0] if task.kind == "text" else task.correct


async def wrong_answer(task: dict[str, Any]) -> Any:
    if task["kind"] == "text":
        return "неверный ответ"
    correct = await correct_answer(task["attempt_task_id"])
    wrong = [o["id"] for o in task["options"] if o["id"] not in correct]
    return wrong[:1]


async def start(client: AsyncClient, user: TestUser, **survey: Any) -> dict[str, Any]:
    response = await client.post(
        f"{API}/attempts", json={**SURVEY, **survey}, headers=user.headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def solve(
    client: AsyncClient, user: TestUser, attempt_id: str, *, correct: bool = True
) -> dict[str, Any]:
    """Отвечает на все задачи попытки; возвращает последний ответ API."""
    while True:
        task = (
            await client.get(
                f"{API}/attempts/{attempt_id}/current-task", headers=user.headers
            )
        ).json()
        answer = (
            await correct_answer(task["attempt_task_id"])
            if correct
            else await wrong_answer(task)
        )
        response = await client.post(
            f"{API}/attempts/{attempt_id}/answers",
            json={"attempt_task_id": task["attempt_task_id"], "answer": answer},
            headers=user.headers,
        )
        assert response.status_code == 200, response.text
        if response.json()["finished"]:
            return response.json()


class FakeChat:
    """Подменяет chat-service: диалоги по id."""

    def __init__(self) -> None:
        self.conversations: dict[uuid.UUID, dict[str, Any]] = {}

    def add(
        self, candidate: TestUser, employer: TestUser, status: str = "open"
    ) -> uuid.UUID:
        conversation_id = uuid.uuid4()
        self.conversations[conversation_id] = {
            "id": str(conversation_id),
            "candidate_id": str(candidate.id),
            "employer_id": str(employer.id),
            "status": status,
            "company_name": "ООО Ромашка",
            "vacancy_title": "Python-разработчик",
        }
        return conversation_id

    async def conversation(self, conversation_id: uuid.UUID) -> dict[str, Any] | None:
        return self.conversations.get(conversation_id)


@pytest.fixture
def chat() -> Iterator[FakeChat]:
    from app.services.employer_tests import get_chat_directory

    fake = FakeChat()
    app.dependency_overrides[get_chat_directory] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_chat_directory, None)
