import copy
from typing import Any

from benefit_common.testing import TestUser
from httpx import AsyncClient

from tests.conftest import API, solve, start
from tests.fixtures import SAMPLE_PACK

ADMIN = f"{API}/admin"


def new_test(slug: str = "frontend-junior", **overrides: Any) -> dict[str, Any]:
    test = copy.deepcopy(SAMPLE_PACK["tests"][0])
    return {
        **test,
        "slug": slug,
        "specialization": "frontend",
        "grade": "junior",
        **overrides,
    }


async def test_admin_api_requires_admin_role(client: AsyncClient) -> None:
    for role in ("candidate", "employer"):
        response = await client.get(f"{ADMIN}/tests", headers=TestUser(role).headers)
        assert response.status_code == 403
    assert (await client.get(f"{ADMIN}/tests")).status_code == 401


async def test_list_and_detail_with_answers(client: AsyncClient) -> None:
    admin = TestUser("admin")
    tests = (await client.get(f"{ADMIN}/tests", headers=admin.headers)).json()
    backend = next(t for t in tests if t["slug"] == "backend-middle")
    assert (backend["tasks_total"], backend["tasks_active"]) == (12, 12)

    detail = (
        await client.get(f"{ADMIN}/tests/{backend['id']}", headers=admin.headers)
    ).json()
    assert detail["tasks"][0]["correct"]


async def test_create_validates_content(client: AsyncClient) -> None:
    admin = TestUser("admin")
    bad_answer = new_test()
    bad_answer["tasks"][0]["correct"] = ["z"]
    too_many = new_test(tasks_per_attempt=50)

    for payload in (bad_answer, too_many):
        response = await client.post(
            f"{ADMIN}/tests", json=payload, headers=admin.headers
        )
        assert response.status_code == 422

    created = await client.post(
        f"{ADMIN}/tests", json=new_test(), headers=admin.headers
    )
    assert created.status_code == 201
    assert created.json()["updated_by"] == str(admin.id)
    duplicate = await client.post(
        f"{ADMIN}/tests", json=new_test(), headers=admin.headers
    )
    assert duplicate.json()["error"]["code"] == "slug_taken"


async def test_replace_deactivates_removed_tasks(
    client: AsyncClient, candidate: TestUser
) -> None:
    admin = TestUser("admin")
    tests = (await client.get(f"{ADMIN}/tests", headers=admin.headers)).json()
    backend = next(t for t in tests if t["slug"] == "backend-middle")
    attempt = await start(client, candidate)
    await solve(client, candidate, attempt["id"])
    detail = (
        await client.get(f"{ADMIN}/tests/{backend['id']}", headers=admin.headers)
    ).json()
    payload = {
        k: v for k, v in detail.items() if k not in ("id", "updated_at", "updated_by")
    }
    payload["tasks"] = payload["tasks"][:9]

    response = await client.put(
        f"{ADMIN}/tests/{backend['id']}", json=payload, headers=admin.headers
    )

    tasks = response.json()["tasks"]
    assert len(tasks) == 12
    assert sum(t["is_active"] for t in tasks) == 9
    # Прошлая попытка по-прежнему открывается.
    old = await client.get(f"{API}/attempts/{attempt['id']}", headers=candidate.headers)
    assert old.json()["result"]["percent"] == 100


async def test_inactive_test_unavailable_to_candidates(
    client: AsyncClient, candidate: TestUser
) -> None:
    admin = TestUser("admin")
    tests = (await client.get(f"{ADMIN}/tests", headers=admin.headers)).json()
    qa = next(t for t in tests if t["slug"] == "qa-junior")

    await client.patch(
        f"{ADMIN}/tests/{qa['id']}", json={"is_active": False}, headers=admin.headers
    )

    survey = (await client.get(f"{API}/survey", headers=candidate.headers)).json()
    grades = {s["id"]: s["grades"] for s in survey["specializations"]}
    assert grades["qa_automation"] == []
    response = await client.post(
        f"{API}/attempts",
        json={
            "industry": "fintech",
            "specialization": "qa_automation",
            "target_grade": "junior",
            "years_of_experience": 1,
        },
        headers=candidate.headers,
    )
    assert response.status_code == 404
    await client.patch(
        f"{ADMIN}/tests/{qa['id']}", json={"is_active": True}, headers=admin.headers
    )


async def test_import_and_export_round_trip(client: AsyncClient) -> None:
    admin = TestUser("admin")
    pack = {
        "format_version": 1,
        "tests": [new_test("devops-senior", specialization="devops", grade="senior")],
    }

    first = await client.post(f"{ADMIN}/import", json=pack, headers=admin.headers)
    again = await client.post(
        f"{ADMIN}/import",
        params={"skip_existing": True},
        json=pack,
        headers=admin.headers,
    )

    assert first.json()["created"] == ["devops-senior"]
    assert again.json()["skipped"] == ["devops-senior"]
    exported = (await client.get(f"{ADMIN}/export", headers=admin.headers)).json()
    slugs = [t["slug"] for t in exported["tests"]]
    assert "devops-senior" in slugs
    devops = next(t for t in exported["tests"] if t["slug"] == "devops-senior")
    original = pack["tests"][0]["tasks"]
    assert [(t["key"], t["correct"]) for t in devops["tasks"]] == [
        (t["key"], t["correct"]) for t in original
    ]


async def test_candidate_never_sees_answers(
    client: AsyncClient, candidate: TestUser
) -> None:
    attempt = await start(client, candidate)
    url = f"{API}/attempts/{attempt['id']}"
    task = await client.get(f"{url}/current-task", headers=candidate.headers)
    await solve(client, candidate, attempt["id"])
    result = await client.get(url, headers=candidate.headers)
    catalog = await client.get(f"{API}/tests", headers=candidate.headers)

    for response in (task, result, catalog):
        assert '"correct"' not in response.text
        assert "explanation" not in response.text
