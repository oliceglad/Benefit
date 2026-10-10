from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from benefit_common.testing import TestUser
from httpx import AsyncClient
from sqlalchemy import update

from app.db.session import async_session_factory
from app.main import app
from app.models import Company
from app.services.registry import (
    RegistryRecord,
    RegistryUnavailableError,
    get_registry,
    parse_rows,
)
from app.services.verification import CompanyVerifier, same_organization_domain
from app.services.website import (
    UnsafeUrlError,
    contains_number,
    ensure_public,
    get_website_checker,
)
from tests.conftest import COMPANY, VACANCY

API = "/api/v1/employers"
INN = COMPANY["inn"]


def record(inn: str = INN, **overrides: Any) -> RegistryRecord:
    values: dict[str, Any] = {
        "inn": inn,
        "kind": "legal",
        "full_name": 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "РОМАШКА"',
        "short_name": 'ООО "РОМАШКА"',
        "ogrn": "1027700132195",
        "kpp": "773601001",
        "registered_at": date(2002, 8, 16),
        "region": "Г.Москва",
        "director": "Генеральный директор: Иванов Иван Иванович",
        "terminated_at": None,
    }
    return RegistryRecord(**(values | overrides))


class FakeRegistry:
    def __init__(self) -> None:
        self.records: dict[str, RegistryRecord] = {INN: record()}
        self.down = False

    async def find(self, inn: str) -> RegistryRecord | None:
        if self.down:
            raise RegistryUnavailableError("down")
        return self.records.get(inn)


class FakeWebsite:
    def __init__(self) -> None:
        self.result: bool | None = True

    async def mentions(self, url: str, needle: str) -> bool | None:
        return self.result


@pytest.fixture
def registry() -> Iterator[FakeRegistry]:
    fake = FakeRegistry()
    app.dependency_overrides[get_registry] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_registry, None)


@pytest.fixture
def website() -> Iterator[FakeWebsite]:
    fake = FakeWebsite()
    app.dependency_overrides[get_website_checker] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_website_checker, None)


async def save(client: AsyncClient, employer: TestUser, **changes: Any) -> dict:
    response = await client.put(
        f"{API}/company", json={**COMPANY, **changes}, headers=employer.headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def verify(client: AsyncClient, employer: TestUser) -> Any:
    return await client.post(f"{API}/company/verification", headers=employer.headers)


def checks(company: dict) -> dict[str, bool | None]:
    return {c["code"]: c["passed"] for c in company["verification"]["checks"]}


# --- Сценарии ---------------------------------------------------------------------


async def test_auto_verification_by_open_sources(
    client: AsyncClient, registry: FakeRegistry, website: FakeWebsite
) -> None:
    employer = TestUser("employer", "hr@romashka.ru")
    company = await save(client, employer, legal_name="Что угодно")
    assert company["verification"]["status"] == "unverified"

    response = await verify(client, employer)

    assert response.status_code == 200, response.text
    company = response.json()
    verification = company["verification"]
    assert (verification["status"], verification["verified_by"]) == (
        "verified",
        "auto",
    )
    assert all(checks(company).values())
    assert verification["registry"]["ogrn"] == "1027700132195"
    # Юридическое наименование — из реестра, а не со слов работодателя.
    assert company["legal_name"].startswith("ОБЩЕСТВО С ОГРАНИЧЕННОЙ")
    await save(client, employer, legal_name="Подмена")
    mine = (await client.get(f"{API}/company", headers=employer.headers)).json()
    assert mine["legal_name"].startswith("ОБЩЕСТВО С ОГРАНИЧЕННОЙ")

    # Кандидат видит значок, но не детали проверок.
    candidate = TestUser("candidate")
    public = (
        await client.get(f"{API}/companies/{company['id']}", headers=candidate.headers)
    ).json()
    assert public["verification"]["is_verified"] is True
    assert "checks" not in public["verification"]
    vacancy = (
        await client.post(f"{API}/vacancies", json=VACANCY, headers=employer.headers)
    ).json()
    assert vacancy["company"]["is_verified"] is True


async def test_public_email_needs_moderator(
    client: AsyncClient, registry: FakeRegistry, website: FakeWebsite
) -> None:
    employer = TestUser("employer", "romashka.hr@mail.ru")
    await save(client, employer)

    company = (await verify(client, employer)).json()

    assert company["verification"]["status"] == "registry_confirmed"
    assert checks(company)["corporate_email"] is False
    assert checks(company)["registry_active"] is True

    # Очередь модератора и решение.
    admin = TestUser("admin")
    queue = (await client.get(f"{API}/admin/companies", headers=admin.headers)).json()
    assert [c["id"] for c in queue] == [company["id"]]
    for user in (employer, TestUser("candidate")):
        forbidden = await client.get(f"{API}/admin/companies", headers=user.headers)
        assert forbidden.status_code == 403
    decided = await client.post(
        f"{API}/admin/companies/{company['id']}/verification",
        json={"decision": "verified", "note": "Проверены документы"},
        headers=admin.headers,
    )
    verification = decided.json()["verification"]
    assert (verification["status"], verification["verified_by"]) == (
        "verified",
        "moderator",
    )

    # Перепроверка сохраняет решение модератора, пока компания действует.
    again = (await verify(client, employer)).json()
    assert again["verification"]["status"] == "verified"


async def test_unknown_and_liquidated_companies_are_rejected(
    client: AsyncClient, registry: FakeRegistry, website: FakeWebsite
) -> None:
    employer = TestUser("employer", "hr@romashka.ru")
    await save(client, employer, inn="7736207543")
    unknown = (await verify(client, employer)).json()
    assert unknown["verification"]["status"] == "rejected"
    assert checks(unknown) == {"registry_found": False}

    registry.records[INN] = record(terminated_at=date(2020, 10, 29))
    await save(client, employer)
    liquidated = (await verify(client, employer)).json()
    assert liquidated["verification"]["status"] == "rejected"
    assert checks(liquidated)["registry_active"] is False


async def test_registry_unavailable_keeps_status(
    client: AsyncClient, registry: FakeRegistry, website: FakeWebsite
) -> None:
    employer = TestUser("employer", "hr@romashka.ru")
    await save(client, employer)
    registry.down = True

    response = await verify(client, employer)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "registry_unavailable"
    mine = (await client.get(f"{API}/company", headers=employer.headers)).json()
    assert mine["verification"]["status"] == "unverified"


async def test_changing_inn_or_site_resets_verification(
    client: AsyncClient, registry: FakeRegistry, website: FakeWebsite
) -> None:
    employer = TestUser("employer", "hr@romashka.ru")
    await save(client, employer)
    await verify(client, employer)

    kept = await save(client, employer, description="Новое описание компании.")
    assert kept["verification"]["status"] == "verified"
    changed = await save(client, employer, website="https://other-company.ru")
    assert changed["verification"]["status"] == "unverified"
    assert changed["verification"]["checks"] == []


async def test_inn_cannot_be_verified_twice(
    client: AsyncClient, registry: FakeRegistry, website: FakeWebsite
) -> None:
    first = TestUser("employer", "hr@romashka.ru")
    await save(client, first)
    await verify(client, first)
    impostor = TestUser("employer", "boss@romashka.ru")
    await save(client, impostor)

    company = (await verify(client, impostor)).json()

    assert company["verification"]["status"] == "registry_confirmed"
    assert checks(company)["inn_unique"] is False


async def test_website_without_inn_or_unreachable(
    client: AsyncClient, registry: FakeRegistry, website: FakeWebsite
) -> None:
    employer = TestUser("employer", "hr@romashka.ru")
    await save(client, employer)

    website.result = None
    company = (await verify(client, employer)).json()
    assert checks(company)["website_mentions_inn"] is None
    assert company["verification"]["status"] == "registry_confirmed"

    nobody = await client.post(
        f"{API}/company/verification", headers=TestUser("employer").headers
    )
    assert nobody.status_code == 404  # профиль компании не заполнен
    await save(client, employer, inn=None)
    no_inn = await verify(client, employer)
    assert no_inn.json()["error"]["code"] == "inn_required"


async def test_liquidation_found_by_scheduled_recheck(
    client: AsyncClient, registry: FakeRegistry, website: FakeWebsite
) -> None:
    employer = TestUser("employer", "hr@romashka.ru")
    await save(client, employer)
    await verify(client, employer)
    async with async_session_factory() as session:
        await session.execute(
            update(Company).values(checked_at=datetime.now(UTC) - timedelta(days=40))
        )
        await session.commit()
    registry.records[INN] = record(terminated_at=date(2026, 9, 1))

    async with async_session_factory() as session:
        assert await CompanyVerifier(session, registry, website).recheck_stale() == 1

    mine = (await client.get(f"{API}/company", headers=employer.headers)).json()
    assert mine["verification"]["status"] == "rejected"


# --- Разбор ответа ЕГРЮЛ и защита запросов к сайту ---------------------------------


def test_parse_egrul_rows() -> None:
    # Реальные ответы egrul.nalog.ru (поле t опущено).
    active = parse_rows(
        "7736207543",
        [
            {
                "c": 'ООО "ЯНДЕКС"',
                "i": "7736207543",
                "k": "ul",
                "n": 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "ЯНДЕКС"',
                "o": "1027700229193",
                "p": "770401001",
                "r": "18.09.2002",
                "rn": "Г.Москва",
            }
        ],
    )
    assert active is not None and active.is_active
    assert (active.ogrn, active.registered_at) == ("1027700229193", date(2002, 9, 18))

    liquidated = parse_rows(
        "2537000000",
        [{"i": "2537000000", "k": "ul", "n": "ЭКСПО-ФИШ", "v": "29.10.2020"}],
    )
    assert liquidated is not None and liquidated.terminated_at == date(2020, 10, 29)

    # ИП: закрытая запись и справочная строка без ИНН.
    closed = parse_rows(
        "500100732259",
        [
            {"i": "500100732259", "k": "fl", "n": "Мясина Е.А.", "e": "31.12.2019"},
            {"cnt": "0", "tot": "0", "k": "sprav-fl"},
        ],
    )
    assert closed is not None and closed.kind == "individual" and not closed.is_active
    # Нечёткий поиск вернул другую организацию — это не совпадение.
    assert parse_rows("7707083893", [{"i": "7707083894", "k": "ul"}]) is None


def test_contains_number_matches_whole_inn() -> None:
    assert contains_number("ИНН 7707083893, КПП 773601001", "7707083893")
    assert contains_number("ИНН: 7707 083 893", "7707083893")
    assert not contains_number("ОГРН 177070838931", "7707083893")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/",
        "http://[::1]/",
        "http://example.com:8080/",
        "ftp://example.com/",
        "http://user:pass@example.com/",
    ],
)
async def test_website_fetch_blocks_internal_addresses(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        await ensure_public(url)


def test_domain_matching() -> None:
    assert same_organization_domain("romashka.ru", "romashka.ru")
    assert same_organization_domain("team.romashka.ru", "careers.romashka.ru") is False
    assert same_organization_domain("team.romashka.ru", "romashka.ru")
    assert not same_organization_domain("romashka.ru.evil.com", "romashka.ru")
