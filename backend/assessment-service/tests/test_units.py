import random
from typing import Any

import pytest
from benefit_common.dictionaries import Grade
from benefit_common.errors import AppError
from benefit_common.settings import get_common_settings
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db.session import async_session_factory
from app.models import Assessment, AssessmentTask, OutboxMessage, Outcome
from app.schemas.content import TestPack
from app.services.attempts import select_tasks
from app.services.content import ContentService
from app.services.delivery import build_relay
from app.services.scoring import evaluate, score, validate_answer
from tests.conftest import solve, start


def task(kind: str, correct: list[str], options: int = 4) -> AssessmentTask:
    return AssessmentTask(
        kind=kind,
        correct=correct,
        options=[{"id": chr(97 + i), "text": str(i)} for i in range(options)],
        skills=[],
    )


@pytest.mark.parametrize(
    ("percent", "target", "expected"),
    [
        (74.9, Grade.MIDDLE, (Outcome.NOT_CONFIRMED, None)),
        (75, Grade.MIDDLE, (Outcome.CONFIRMED, Grade.MIDDLE)),
        (89.9, Grade.MIDDLE, (Outcome.CONFIRMED, Grade.MIDDLE)),
        (90, Grade.MIDDLE, (Outcome.EXCEEDED, Grade.SENIOR)),
        (100, Grade.LEAD, (Outcome.CONFIRMED, Grade.LEAD)),
    ],
)
def test_evaluate_thresholds(
    percent: float, target: Grade, expected: tuple[Outcome, Grade | None]
) -> None:
    assert evaluate(percent, target) == expected


def test_multiple_choice_partial_credit() -> None:
    t = task("multiple_choice", ["a", "b", "d"])
    assert score(t, ["a", "b", "d"]) == (1.0, True)
    assert score(t, ["a", "b"]) == pytest.approx((2 / 3, False))
    assert score(t, ["a", "b", "c"]) == pytest.approx((1 / 3, False))
    assert score(t, ["c"]) == (0.0, False)


def test_text_answer_normalized() -> None:
    t = task("text", ["Ответ"], options=0)
    assert score(t, validate_answer(t, "  ОТВЕТ ")) == (1.0, True)
    with pytest.raises(AppError):
        validate_answer(t, ["ответ"])


def test_select_tasks_prefers_candidate_skills() -> None:
    bank = [
        AssessmentTask(key=f"t{i}", position=i, skills=[skill])
        for i, skill in enumerate(["Docker", "Python", "SQL", "Python", "Docker"])
    ]
    chosen = select_tasks(bank, {"python"}, 2, random.Random(1))
    assert {t.skills[0] for t in chosen} == {"Python"}


async def test_import_is_idempotent() -> None:
    from tests.fixtures import SAMPLE_PACK

    count = (
        select(func.count(AssessmentTask.id))
        .join(Assessment)
        .where(Assessment.slug.in_(["backend-middle", "qa-junior"]))
    )
    async with async_session_factory() as session:
        before = await session.scalar(count)
        report = await ContentService(session).import_pack(
            TestPack.model_validate(SAMPLE_PACK), None, skip_existing=True
        )
        after = await session.scalar(count)
    assert before == after == 22
    assert report.skipped == ["backend-middle", "qa-junior"]


async def test_relay_delivers_results(client: AsyncClient, candidate: Any) -> None:
    attempt = await start(client, candidate)
    await solve(client, candidate, attempt["id"])
    delivered: dict[str, list[dict]] = {"candidate": [], "notification": []}

    async def to_candidate(payload: dict) -> None:
        delivered["candidate"].append(payload)

    async def to_notifications(payload: dict) -> None:
        delivered["notification"].append(payload)

    relay = build_relay(async_session_factory, to_candidate, to_notifications)
    assert await relay.process_batch() == 2

    assert delivered["candidate"][0]["verified_grade"] == "senior"
    assert delivered["notification"][0]["title"].startswith("Тест пройден")
    async with async_session_factory() as session:
        pending = await session.scalar(
            select(func.count()).where(OutboxMessage.sent_at.is_(None))
        )
    assert pending == 0


async def test_internal_status(client: AsyncClient, candidate: Any) -> None:
    attempt = await start(client, candidate)
    await solve(client, candidate, attempt["id"])
    url = f"/internal/v1/candidates/{candidate.id}/status"

    assert (await client.get(url)).status_code == 401
    response = await client.get(
        url, headers={"X-Internal-Token": get_common_settings().internal_api_token}
    )
    assert response.json()["verified"]["grade"] == "senior"
