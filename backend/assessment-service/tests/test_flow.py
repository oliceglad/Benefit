from datetime import timedelta

import pytest
from benefit_common.testing import TestUser
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_factory
from app.models import OutboxMessage
from app.services import clock
from tests.conftest import API, SURVEY, FakeCandidates, solve, start


async def outbox(kind: str) -> list[dict]:
    async with async_session_factory() as session:
        rows = await session.scalars(
            select(OutboxMessage).where(OutboxMessage.kind == kind)
        )
        return [row.payload for row in rows]


async def test_survey_prefilled_from_profile(
    client: AsyncClient, candidate: TestUser
) -> None:
    body = (await client.get(f"{API}/survey", headers=candidate.headers)).json()

    assert body["prefill"] == {
        "industry": "fintech",
        "specialization": "backend",
        "claimed_grade": "middle",
        "years_of_experience": 3.5,
        "skills": ["Python", "PostgreSQL"],
    }
    grades = {s["id"]: s["grades"] for s in body["specializations"]}
    assert grades["backend"] == ["middle"]
    assert grades["qa_automation"] == ["junior"]
    assert body["pass_percent"] == 75


async def test_access_control(
    client: AsyncClient, candidate: TestUser, candidates: FakeCandidates
) -> None:
    attempt = await start(client, candidate)
    other = TestUser("candidate")
    employer = TestUser("employer")
    url = f"{API}/attempts/{attempt['id']}"

    assert (await client.get(url, headers=other.headers)).status_code == 404
    assert (await client.get(url, headers=employer.headers)).status_code == 403
    assert (await client.get(f"{API}/survey")).status_code == 401


async def test_attempt_requires_profile_and_existing_test(
    client: AsyncClient, candidates: FakeCandidates
) -> None:
    user = TestUser("candidate")
    response = await client.post(f"{API}/attempts", json=SURVEY, headers=user.headers)
    assert response.json()["error"]["code"] == "profile_required"

    candidates.profiles[user.id] = {"grade": None, "skills": []}
    response = await client.post(
        f"{API}/attempts",
        json={**SURVEY, "specialization": "frontend"},
        headers=user.headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "assessment_not_found"


async def test_all_correct_exceeds_target_grade(
    client: AsyncClient, candidate: TestUser
) -> None:
    attempt = await start(client, candidate)
    assert attempt["total_tasks"] == 8
    assert attempt["claimed_grade"] == "middle"

    final = await solve(client, candidate, attempt["id"])

    result = final["attempt"]["result"]
    assert final["attempt"]["status"] == "completed"
    assert result["percent"] == 100
    assert result["score"] == result["max_score"] == final["attempt"]["max_score"]
    assert (result["outcome"], result["confirmed_grade"]) == ("exceeded", "senior")
    assert all(t["time_spent_seconds"] is not None for t in result["tasks"])
    assert sum(t["max_points"] for t in result["tasks"]) == result["max_score"]
    assert result["duration_seconds"] >= 0
    assert {s["skill"] for s in result["skills"]} >= {"Python"}

    [push] = await outbox("candidate.assessment")
    assert push["verified_grade"] == "senior"
    assert push["specialization"] == "backend"
    assert push["industry"] == "fintech"
    assert push["percent"] == 100
    [notification] = await outbox("notification")
    assert notification["user_id"] == str(candidate.id)
    assert notification["type"] == "assessment.completed"
    assert notification["dedup_key"] == f"assessment:{attempt['id']}:finished"


async def test_pass_threshold_confirms_target_grade(
    client: AsyncClient, candidate: TestUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "exceed_percent", 101.0)
    attempt = await start(client, candidate)

    final = await solve(client, candidate, attempt["id"])

    result = final["attempt"]["result"]
    assert (result["outcome"], result["confirmed_grade"]) == ("confirmed", "middle")
    [push] = await outbox("candidate.assessment")
    assert push["verified_grade"] == "middle"


async def test_failed_attempt_does_not_downgrade(
    client: AsyncClient, candidate: TestUser
) -> None:
    attempt = await start(client, candidate)

    final = await solve(client, candidate, attempt["id"], correct=False)

    result = final["attempt"]["result"]
    assert result["outcome"] == "not_confirmed"
    assert result["confirmed_grade"] is None
    assert result["percent"] < 75
    assert "не подтверждён" in result["message"]
    [push] = await outbox("candidate.assessment")
    assert push["verified_grade"] is None  # низкий грейд не передаётся


async def test_task_time_limit(
    client: AsyncClient, candidate: TestUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempt = await start(client, candidate)
    url = f"{API}/attempts/{attempt['id']}"
    task = (await client.get(f"{url}/current-task", headers=candidate.headers)).json()
    assert task["time_left_seconds"] <= task["time_limit_seconds"]
    assert "correct" not in task

    # «Перематываем» время за лимит задачи (но в пределах лимита теста).
    late = clock.now() + timedelta(seconds=task["time_limit_seconds"] + 30)
    monkeypatch.setattr(clock, "now", lambda: late)
    from tests.conftest import correct_answer

    response = await client.post(
        f"{url}/answers",
        json={
            "attempt_task_id": task["attempt_task_id"],
            "answer": await correct_answer(task["attempt_task_id"]),
        },
        headers=candidate.headers,
    )

    body = response.json()
    assert body["timed_out"] is True
    assert body["time_spent_seconds"] >= task["time_limit_seconds"] + 30
    finished = (await client.post(f"{url}/finish", headers=candidate.headers)).json()
    first = finished["result"]["tasks"][0]
    assert (first["points_awarded"], first["is_correct"]) == (0, False)
    assert all(t["skipped"] for t in finished["result"]["tasks"][1:])


async def test_attempt_expires_after_time_limit(
    client: AsyncClient, candidate: TestUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempt = await start(client, candidate)
    later = clock.now() + timedelta(
        seconds=attempt["assessment"]["time_limit_seconds"] + 60
    )
    monkeypatch.setattr(clock, "now", lambda: later)

    body = (
        await client.get(f"{API}/attempts/{attempt['id']}", headers=candidate.headers)
    ).json()

    assert body["status"] == "expired"
    assert body["result"]["percent"] == 0
    response = await client.get(
        f"{API}/attempts/{attempt['id']}/current-task", headers=candidate.headers
    )
    assert response.json()["error"]["code"] == "attempt_finished"


async def test_only_current_task_can_be_answered(
    client: AsyncClient, candidate: TestUser
) -> None:
    attempt = await start(client, candidate)
    url = f"{API}/attempts/{attempt['id']}"

    response = await client.post(
        f"{url}/answers",
        json={"attempt_task_id": attempt["id"], "answer": ["a"]},
        headers=candidate.headers,
    )
    assert response.json()["error"]["code"] == "not_current_task"

    task = (await client.get(f"{url}/current-task", headers=candidate.headers)).json()
    response = await client.post(
        f"{url}/answers",
        json={"attempt_task_id": task["attempt_task_id"], "answer": ["zzz"]},
        headers=candidate.headers,
    )
    assert response.status_code == 422


async def test_one_active_attempt_and_cooldown(
    client: AsyncClient, candidate: TestUser, candidates: FakeCandidates
) -> None:
    attempt = await start(client, candidate)
    response = await client.post(
        f"{API}/attempts", json=SURVEY, headers=candidate.headers
    )
    assert response.json()["error"]["code"] == "attempt_in_progress"

    await client.post(
        f"{API}/attempts/{attempt['id']}/finish", headers=candidate.headers
    )
    response = await client.post(
        f"{API}/attempts", json=SURVEY, headers=candidate.headers
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "attempt_cooldown"

    # Другая специализация доступна сразу.
    await start(
        client, candidate, specialization="qa_automation", target_grade="junior"
    )
    status = (await client.get(f"{API}/status", headers=candidate.headers)).json()
    assert [c["specialization"] for c in status["cooldowns"]] == ["backend"]
    assert status["active_attempt_id"] is not None


async def test_best_confirmation_survives_failed_attempt(
    client: AsyncClient, candidate: TestUser
) -> None:
    first = await start(client, candidate)
    await solve(client, candidate, first["id"])  # senior (exceeded)
    second = await start(
        client, candidate, specialization="qa_automation", target_grade="junior"
    )

    await solve(client, candidate, second["id"], correct=False)

    pushes = await outbox("candidate.assessment")
    assert pushes[-1]["verified_grade"] == "senior"
    assert pushes[-1]["specialization"] == "backend"
    status = (await client.get(f"{API}/status", headers=candidate.headers)).json()
    assert status["verified"]["grade"] == "senior"
    history = (await client.get(f"{API}/attempts", headers=candidate.headers)).json()
    assert [h["outcome"] for h in history] == ["not_confirmed", "exceeded"]
    assert history[0]["industry"] == "fintech"
