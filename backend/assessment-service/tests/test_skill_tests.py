import copy
from datetime import timedelta
from typing import Any

import pytest
from benefit_common.testing import TestUser
from httpx import AsyncClient

from app.core.config import settings
from app.services import clock
from tests.conftest import API, FakeCandidates, correct_answer, wrong_answer
from tests.fixtures import SAMPLE_PACK
from tests.test_flow import outbox

ADMIN = f"{API}/admin"


async def english(client: AsyncClient, user: TestUser) -> dict[str, Any]:
    [option] = (await client.get(f"{API}/skill-tests", headers=user.headers)).json()
    return option


async def take(
    client: AsyncClient, user: TestUser, test_id: str, *, correct: int
) -> dict[str, Any]:
    """Проходит тест на навык: ``correct`` верных ответов, остальные — неверные."""
    response = await client.post(
        f"{API}/skill-tests/{test_id}/attempts", headers=user.headers
    )
    assert response.status_code == 201, response.text
    attempt_id = response.json()["id"]
    answered = 0
    while True:
        task = (
            await client.get(
                f"{API}/attempts/{attempt_id}/current-task", headers=user.headers
            )
        ).json()
        answer = (
            await correct_answer(task["attempt_task_id"])
            if answered < correct
            else await wrong_answer(task)
        )
        answered += 1
        response = await client.post(
            f"{API}/attempts/{attempt_id}/answers",
            json={"attempt_task_id": task["attempt_task_id"], "answer": answer},
            headers=user.headers,
        )
        assert response.status_code == 200, response.text
        if response.json()["finished"]:
            return response.json()["attempt"]


async def test_skill_catalog_is_separate_from_grade_survey(
    client: AsyncClient, candidate: TestUser
) -> None:
    option = await english(client, candidate)

    assert option["test"]["kind"] == "skill"
    assert option["test"]["skill"] == "English"
    assert [level["id"] for level in option["test"]["levels"]] == [
        "a2",
        "b1",
        "b2",
        "c1",
    ]
    assert (option["verified"], option["available_at"]) == (None, None)
    by_kind = {
        kind: (
            await client.get(
                f"{API}/tests", params={"kind": kind}, headers=candidate.headers
            )
        ).json()
        for kind in ("grade", "skill")
    }
    assert "english" in {t["slug"] for t in by_kind["skill"]}
    # Опрос теста на грейд строится только по тестам на грейд.
    assert all(t["skill"] is None for t in by_kind["grade"])
    survey = (await client.get(f"{API}/survey", headers=candidate.headers)).json()
    offered = sum(len(s["grades"]) for s in survey["specializations"])
    assert offered == len(by_kind["grade"])


async def test_level_is_the_highest_threshold_reached(
    client: AsyncClient, candidate: TestUser
) -> None:
    option = await english(client, candidate)

    attempt = await take(client, candidate, option["test"]["id"], correct=8)

    result = attempt["result"]
    assert result["percent"] == 80
    assert (result["outcome"], result["level"]["id"]) == ("confirmed", "b2")
    assert (result["skill"], result["target_grade"]) == ("English", None)
    assert "B2" in result["message"]

    [push] = await outbox("candidate.skill")
    assert push["skill"] == "English"
    assert push["verification"]["level"]["id"] == "b2"
    assert push["verification"]["attempt_id"] == attempt["id"]
    # Грейд тест на навык не трогает.
    assert await outbox("candidate.assessment") == []
    [notification] = await outbox("notification")
    assert "B2" in notification["title"]

    status = (await client.get(f"{API}/status", headers=candidate.headers)).json()
    assert [(s["skill"], s["level"]["id"]) for s in status["skills"]] == [
        ("English", "b2")
    ]
    assert status["verified"] is None
    [summary] = (await client.get(f"{API}/attempts", headers=candidate.headers)).json()
    assert (summary["kind"], summary["level"]["id"]) == ("skill", "b2")


async def test_below_scale_and_cooldown_per_skill(
    client: AsyncClient, candidate: TestUser
) -> None:
    option = await english(client, candidate)
    test_id = option["test"]["id"]

    attempt = await take(client, candidate, test_id, correct=2)

    result = attempt["result"]
    assert (result["outcome"], result["level"]) == ("not_confirmed", None)
    assert "не подтверждён" in result["message"]
    [push] = await outbox("candidate.skill")
    assert push["verification"] is None

    retry = await client.post(
        f"{API}/skill-tests/{test_id}/attempts", headers=candidate.headers
    )
    assert retry.status_code == 429
    assert (await english(client, candidate))["available_at"] is not None
    # Кулдаун навыка не мешает тесту на грейд.
    grade = await client.post(
        f"{API}/attempts",
        json={
            "industry": "fintech",
            "specialization": "backend",
            "target_grade": "middle",
            "years_of_experience": 3,
        },
        headers=candidate.headers,
    )
    assert grade.status_code == 201


async def test_best_level_survives_worse_retake(
    client: AsyncClient, candidate: TestUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_id = (await english(client, candidate))["test"]["id"]
    await take(client, candidate, test_id, correct=9)  # C1

    later = clock.now() + timedelta(hours=settings.attempt_cooldown_hours + 1)
    monkeypatch.setattr(clock, "now", lambda: later)
    await take(client, candidate, test_id, correct=5)  # B1

    pushes = await outbox("candidate.skill")
    assert pushes[-1]["verification"]["level"]["id"] == "c1"
    verified = (await english(client, candidate))["verified"]
    assert verified["level"]["id"] == "c1"


async def test_skill_test_requires_profile_and_skill_kind(
    client: AsyncClient, candidates: FakeCandidates, candidate: TestUser
) -> None:
    stranger = TestUser("candidate")
    test_id = (await english(client, candidate))["test"]["id"]
    response = await client.post(
        f"{API}/skill-tests/{test_id}/attempts", headers=stranger.headers
    )
    assert response.json()["error"]["code"] == "profile_required"

    grade_test = next(
        t
        for t in (await client.get(f"{API}/tests", headers=candidate.headers)).json()
        if t["kind"] == "grade"
    )
    response = await client.post(
        f"{API}/skill-tests/{grade_test['id']}/attempts", headers=candidate.headers
    )
    assert response.status_code == 404


async def test_content_validation_for_skill_tests(client: AsyncClient) -> None:
    admin = TestUser("admin")
    source = copy.deepcopy(SAMPLE_PACK["tests"][2])

    no_levels = {**source, "slug": "sql", "skill": "SQL", "levels": []}
    unsorted = {
        **source,
        "slug": "sql",
        "skill": "SQL",
        "levels": list(reversed(source["levels"])),
    }
    with_grade = {**source, "slug": "sql", "skill": "SQL", "grade": "middle"}
    for payload in (no_levels, unsorted, with_grade):
        response = await client.post(
            f"{ADMIN}/tests", json=payload, headers=admin.headers
        )
        assert response.status_code == 422, payload

    # Второй активный тест на тот же навык — конфликт: кандидат не выберет.
    duplicate = await client.post(
        f"{ADMIN}/tests",
        json={**source, "slug": "english-2", "skill": "english"},
        headers=admin.headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "assessment_duplicate"

    created = await client.post(
        f"{ADMIN}/tests",
        json={**source, "slug": "sql", "skill": "SQL"},
        headers=admin.headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["levels"] == source["levels"]
    summary = next(
        t
        for t in (await client.get(f"{ADMIN}/tests", headers=admin.headers)).json()
        if t["slug"] == "sql"
    )
    assert (summary["kind"], summary["skill"], summary["grade"]) == (
        "skill",
        "SQL",
        None,
    )
    await client.patch(
        f"{ADMIN}/tests/{created.json()['id']}",
        json={"is_active": False},
        headers=admin.headers,
    )
