from typing import Any

from benefit_common.testing import TestUser
from httpx import AsyncClient

from tests.conftest import COMPANY, VACANCY

API = "/api/v1/employers"
CATALOG = "/api/v1/vacancies"


async def employer_with_company(client: AsyncClient) -> TestUser:
    employer = TestUser("employer")
    response = await client.put(
        f"{API}/company", json=COMPANY, headers=employer.headers
    )
    assert response.status_code == 200, response.text
    return employer


async def create(client: AsyncClient, employer: TestUser, **changes: Any) -> dict:
    response = await client.post(
        f"{API}/vacancies", json={**VACANCY, **changes}, headers=employer.headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def set_status(
    client: AsyncClient, employer: TestUser, vacancy: dict, status: str
) -> Any:
    return await client.patch(
        f"{API}/vacancies/{vacancy['id']}",
        json={"status": status},
        headers=employer.headers,
    )


async def test_full_vacancy_model(client: AsyncClient) -> None:
    employer = await employer_with_company(client)

    vacancy = await create(client, employer, salary_type="net")

    assert vacancy["required_skills"] == ["Python", "FastAPI"]
    assert vacancy["optional_skills"] == ["Kafka"]
    assert vacancy["responsibilities"][0] == "Разрабатывать сервисы приёма платежей"
    assert vacancy["salary_type"] == "net"
    assert vacancy["publish_blockers"] == []


async def test_skill_cannot_be_required_and_optional(client: AsyncClient) -> None:
    employer = await employer_with_company(client)

    response = await client.post(
        f"{API}/vacancies",
        json={**VACANCY, "optional_skills": ["python"]},
        headers=employer.headers,
    )

    assert response.status_code == 422
    assert "Python" in response.json()["error"]["message"] + str(
        response.json()["error"]["details"]
    )


async def test_publishing_requires_skills_and_responsibilities(
    client: AsyncClient,
) -> None:
    employer = await employer_with_company(client)
    draft = await create(client, employer, required_skills=[], responsibilities=[])
    assert draft["publish_blockers"] == ["required_skills", "responsibilities"]

    response = await set_status(client, employer, draft, "published")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "vacancy_incomplete"
    assert [d["field"] for d in error["details"]] == [
        "required_skills",
        "responsibilities",
    ]

    # Опубликованную вакансию нельзя «опустошить» правкой.
    full = await create(client, employer)
    await set_status(client, employer, full, "published")
    emptied = await client.put(
        f"{API}/vacancies/{full['id']}",
        json={**VACANCY, "responsibilities": []},
        headers=employer.headers,
    )
    assert emptied.json()["error"]["code"] == "vacancy_incomplete"


async def test_lifecycle_close_reopen_archive_restore(client: AsyncClient) -> None:
    employer = await employer_with_company(client)
    candidate = TestUser("candidate")
    vacancy = await create(client, employer)

    published = (await set_status(client, employer, vacancy, "published")).json()
    first_published_at = published["published_at"]
    closed = (await set_status(client, employer, vacancy, "closed")).json()
    assert closed["closed_at"] is not None
    reopened = (await set_status(client, employer, vacancy, "published")).json()
    assert (reopened["closed_at"], reopened["published_at"]) == (
        None,
        first_published_at,
    )

    archived = (await set_status(client, employer, vacancy, "archived")).json()
    assert archived["archived_at"] is not None
    # Архив скрыт из каталога и из списка по умолчанию.
    catalog = await client.get(CATALOG, headers=candidate.headers)
    assert catalog.json()["total"] == 0
    mine = await client.get(f"{API}/vacancies", headers=employer.headers)
    assert mine.json() == []
    archive = await client.get(
        f"{API}/vacancies", params={"status": "archived"}, headers=employer.headers
    )
    assert [v["id"] for v in archive.json()] == [vacancy["id"]]

    # В архиве не редактируется и не публикуется напрямую.
    edit = await client.put(
        f"{API}/vacancies/{vacancy['id']}", json=VACANCY, headers=employer.headers
    )
    assert edit.json()["error"]["code"] == "vacancy_archived"
    direct = await set_status(client, employer, vacancy, "published")
    assert direct.status_code == 409

    restored = (await set_status(client, employer, vacancy, "draft")).json()
    assert (restored["status"], restored["archived_at"]) == ("draft", None)


async def test_catalog_filters_by_any_skill_and_tax_mode(client: AsyncClient) -> None:
    employer = await employer_with_company(client)
    candidate = TestUser("candidate")
    gross = await create(client, employer)
    net = await create(
        client,
        employer,
        title="Go Developer",
        required_skills=["Go"],
        optional_skills=["Python"],
        salary_type="net",
    )
    for vacancy in (gross, net):
        await set_status(client, employer, vacancy, "published")

    async def ids(**params: Any) -> set[str]:
        page = await client.get(CATALOG, params=params, headers=candidate.headers)
        return {v["id"] for v in page.json()["items"]}

    # Навык ищется и в обязательных, и в желательных.
    assert await ids(skill="python") == {gross["id"], net["id"]}
    assert await ids(skill="kafka") == {gross["id"]}
    assert await ids(salary_type="net") == {net["id"]}
