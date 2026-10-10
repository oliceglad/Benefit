"""Проверка компании по открытому реестру ФНС (ЕГРЮЛ / ЕГРИП).

Используется публичный поиск https://egrul.nalog.ru: по ИНН он возвращает
наименование, ОГРН, КПП, дату регистрации, регион, руководителя и дату
прекращения деятельности (ликвидация юрлица или закрытие ИП). Ключ доступа
не нужен.

``CompanyRegistry`` — интерфейс: при необходимости источник заменяется
(например, на DaData или API ФНС «Прозрачный бизнес»), не меняя остальной код.
"""

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class RegistryUnavailableError(Exception):
    """Реестр не ответил или потребовал капчу — проверку нужно повторить."""


@dataclass(frozen=True)
class RegistryRecord:
    inn: str
    # legal — юрлицо (ЕГРЮЛ), individual — индивидуальный предприниматель.
    kind: str
    full_name: str
    short_name: str | None
    ogrn: str | None
    kpp: str | None
    registered_at: date | None
    region: str | None
    director: str | None
    # Дата ликвидации / прекращения деятельности ИП.
    terminated_at: date | None

    @property
    def is_active(self) -> bool:
        return self.terminated_at is None

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("registered_at", "terminated_at"):
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data


class CompanyRegistry(Protocol):
    async def find(self, inn: str) -> RegistryRecord | None:
        """Запись реестра по ИНН; ``None`` — такого ИНН в реестре нет.

        Raises:
            RegistryUnavailableError: реестр сейчас недоступен.
        """
        ...


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        return None


def parse_rows(inn: str, rows: list[dict[str, Any]]) -> RegistryRecord | None:
    """Разбор ответа поиска ЕГРЮЛ.

    Поиск нечёткий, поэтому берём только записи с точно таким ИНН. У ИП
    бывает несколько записей (закрытые и действующая) — действующая важнее.
    Ключи ответа: n — полное наименование, c — краткое, o — ОГРН(ИП),
    p — КПП, r — дата регистрации, rn — регион, g — руководитель,
    v / e — дата прекращения деятельности юрлица / ИП, k — ul | fl.
    """
    matches = [
        row for row in rows if row.get("i") == inn and row.get("k") in ("ul", "fl")
    ]
    if not matches:
        return None
    row = min(matches, key=lambda r: bool(r.get("v") or r.get("e")))
    director = row.get("g")
    return RegistryRecord(
        inn=inn,
        kind="legal" if row["k"] == "ul" else "individual",
        full_name=row.get("n") or row.get("c") or "",
        short_name=row.get("c"),
        ogrn=row.get("o"),
        kpp=row.get("p"),
        registered_at=_date(row.get("r")),
        region=row.get("rn"),
        # «Директор: Иванов Иван Иванович» → руководитель с должностью.
        director=director.strip() if director else None,
        terminated_at=_date(row.get("v") or row.get("e")),
    )


class EgrulRegistry:
    """Публичный поиск ЕГРЮЛ/ЕГРИП ФНС: запрос → токен → результат."""

    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def find(self, inn: str) -> RegistryRecord | None:
        headers = {"User-Agent": "Benefit/1.0 (company verification)"}
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, headers=headers
            ) as client:
                started = await client.post(f"{self.base_url}/", data={"query": inn})
                started.raise_for_status()
                ticket = started.json()
                if ticket.get("captchaRequired") or not ticket.get("t"):
                    raise RegistryUnavailableError("captcha required")
                # Результат готовится асинхронно: несколько коротких попыток.
                for attempt in range(4):
                    await asyncio.sleep(0.5 + attempt * 0.5)
                    response = await client.get(
                        f"{self.base_url}/search-result/{ticket['t']}"
                    )
                    response.raise_for_status()
                    result = response.json()
                    if "rows" in result:
                        return parse_rows(inn, result["rows"])
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("EGRUL lookup failed: %s", exc)
            raise RegistryUnavailableError(str(exc)) from exc
        raise RegistryUnavailableError("search result not ready")


def get_registry() -> CompanyRegistry:
    return EgrulRegistry(settings.egrul_url, settings.registry_timeout_seconds)
