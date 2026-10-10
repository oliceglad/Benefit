"""Проверка компании и работодателя по открытым источникам.

Реестр ФНС подтверждает, что компания существует и действует, но не то,
что пользователь её представляет: ИНН известной компании может указать
кто угодно. Поэтому статус «Проверенный работодатель» выставляется
автоматически, только если связь доказана:

1. ИНН есть в ЕГРЮЛ/ЕГРИП, деятельность не прекращена;
2. почта аккаунта корпоративная (не публичный почтовый сервис);
3. домен почты совпадает с доменом сайта компании;
4. на сайте компании опубликован этот ИНН;
5. ИНН не подтверждён за другим работодателем.

Если реестр компанию подтвердил, а остальные условия не выполнены, статус
— ``registry_confirmed``: решение принимает модератор (``/admin``).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from benefit_common.errors import AppError, ConflictError, ServiceUnavailableError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Company, VerificationStatus
from app.services.registry import (
    CompanyRegistry,
    RegistryRecord,
    RegistryUnavailableError,
)
from app.services.website import WebsiteChecker

logger = logging.getLogger(__name__)

# Бесплатные почтовые сервисы: такой адрес не связывает человека с компанией.
PUBLIC_MAIL_DOMAINS = frozenset(
    {
        "mail.ru", "bk.ru", "inbox.ru", "list.ru", "internet.ru", "xmail.ru",
        "yandex.ru", "ya.ru", "yandex.com", "yandex.by", "yandex.kz",
        "narod.ru", "rambler.ru", "lenta.ru", "autorambler.ru",
        "myrambler.ru", "ro.ru", "rambler.ua", "qip.ru", "pochta.ru",
        "gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
        "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
        "yahoo.com", "proton.me", "protonmail.com", "pm.me", "mail.com",
        "gmx.com", "gmx.net", "zoho.com", "aol.com", "tutanota.com",
    }
)  # fmt: skip


@dataclass
class Check:
    code: str
    # None — проверить не удалось (например, сайт не ответил).
    passed: bool | None
    message: str

    def to_json(self) -> dict[str, Any]:
        return {"code": self.code, "passed": self.passed, "message": self.message}


def site_domain(url: str | None) -> str | None:
    if not url:
        return None
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return host.removeprefix("www.") or None


def email_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[1].lower().rstrip(".")


def same_organization_domain(email_host: str, site_host: str) -> bool:
    """hr@company.ru и company.ru, hr@team.company.ru и careers.company.ru."""
    return (
        email_host == site_host
        or email_host.endswith("." + site_host)
        or site_host.endswith("." + email_host)
    )


def reset_verification(company: Company) -> None:
    """Изменились данные, на которых основана проверка, — статус снимается."""
    company.verification_status = VerificationStatus.UNVERIFIED
    company.verification_checks = []
    company.registry_data = None
    company.verified_by = None
    company.verification_note = None
    company.verified_at = None
    company.checked_at = None


class CompanyVerifier:
    def __init__(
        self,
        session: AsyncSession,
        registry: CompanyRegistry,
        website: WebsiteChecker,
    ) -> None:
        self.session = session
        self.registry = registry
        self.website = website

    async def verify(self, company: Company, owner_email: str | None) -> Company:
        """Полная проверка по запросу работодателя."""
        if not company.inn:
            raise AppError(
                "Укажите ИНН компании, чтобы пройти проверку",
                code="inn_required",
                status_code=422,
            )
        record = await self._lookup(company.inn)
        checks: list[Check] = []
        now = datetime.now(UTC)
        company.checked_at = now
        if not self._apply_registry(company, record, checks):
            company.verification_checks = [c.to_json() for c in checks]
            await self.session.commit()
            await self.session.refresh(company)
            return company

        checks += await self._ownership_checks(company, owner_email)
        company.verification_checks = [c.to_json() for c in checks]
        moderator_approved = (
            company.verification_status == VerificationStatus.VERIFIED
            and company.verified_by == "moderator"
        )
        if all(c.passed for c in checks):
            if not moderator_approved:
                company.verified_by = "auto"
                company.verified_at = now
            company.verification_status = VerificationStatus.VERIFIED
        elif not moderator_approved:
            # Решение модератора сохраняется при перепроверке, пока
            # компания действует.
            company.verification_status = VerificationStatus.REGISTRY_CONFIRMED
            company.verified_by = None
            company.verified_at = None
        await self.session.commit()
        await self.session.refresh(company)
        return company

    async def recheck_registry(self, company: Company) -> None:
        """Плановая перепроверка: только реестр (ликвидация снимает статус)."""
        assert company.inn
        record = await self._lookup(company.inn)
        company.checked_at = datetime.now(UTC)
        checks: list[Check] = []
        if not self._apply_registry(company, record, checks):
            company.verification_checks = [c.to_json() for c in checks]
        await self.session.commit()

    async def recheck_stale(self, limit: int = 20) -> int:
        threshold = datetime.now(UTC) - timedelta(
            days=settings.verification_recheck_days
        )
        companies = list(
            await self.session.scalars(
                select(Company)
                .where(
                    Company.verification_status.in_(
                        [
                            VerificationStatus.VERIFIED,
                            VerificationStatus.REGISTRY_CONFIRMED,
                        ]
                    ),
                    Company.checked_at < threshold,
                )
                .order_by(Company.checked_at)
                .limit(limit)
            )
        )
        for company in companies:
            try:
                await self.recheck_registry(company)
            except ServiceUnavailableError:
                # Реестр недоступен — попробуем в следующий раз.
                await self.session.rollback()
                break
        return len(companies)

    async def moderate(
        self, company: Company, decision: str, note: str | None
    ) -> Company:
        if decision == VerificationStatus.VERIFIED:
            registry = company.registry_data or {}
            if not registry or registry.get("terminated_at"):
                raise ConflictError(
                    "Подтвердить можно только компанию, найденную в реестре "
                    "и действующую",
                    code="registry_not_confirmed",
                )
            company.verification_status = VerificationStatus.VERIFIED
            company.verified_by = "moderator"
            company.verified_at = datetime.now(UTC)
        else:
            company.verification_status = VerificationStatus.REJECTED
            company.verified_by = "moderator"
            company.verified_at = None
        company.verification_note = note
        await self.session.commit()
        await self.session.refresh(company)
        return company

    # --- Внутреннее ------------------------------------------------------------------

    async def _lookup(self, inn: str) -> RegistryRecord | None:
        try:
            return await self.registry.find(inn)
        except RegistryUnavailableError as exc:
            raise ServiceUnavailableError(
                "Реестр ФНС (egrul.nalog.ru) сейчас недоступен. Повторите "
                "проверку через несколько минут",
                code="registry_unavailable",
            ) from exc

    @staticmethod
    def _apply_registry(
        company: Company, record: RegistryRecord | None, checks: list[Check]
    ) -> bool:
        """Результат реестра; ``False`` — компания не прошла проверку."""
        if record is None:
            checks.append(
                Check(
                    "registry_found",
                    False,
                    "ИНН не найден в ЕГРЮЛ/ЕГРИП — проверьте номер",
                )
            )
            company.registry_data = None
            company.verification_status = VerificationStatus.REJECTED
            company.verified_by = "auto"
            company.verified_at = None
            return False
        company.registry_data = record.to_json()
        kind = "ЕГРЮЛ" if record.kind == "legal" else "ЕГРИП"
        checks.append(Check("registry_found", True, f"Компания найдена в {kind}"))
        if not record.is_active:
            assert record.terminated_at
            checks.append(
                Check(
                    "registry_active",
                    False,
                    f"Деятельность прекращена {record.terminated_at:%d.%m.%Y}",
                )
            )
            company.verification_status = VerificationStatus.REJECTED
            company.verified_by = "auto"
            company.verified_at = None
            return False
        checks.append(Check("registry_active", True, "Компания действует"))
        # Юридическое наименование — из реестра, а не со слов работодателя.
        company.legal_name = record.full_name[:300]
        return True

    async def _ownership_checks(
        self, company: Company, owner_email: str | None
    ) -> list[Check]:
        checks: list[Check] = []
        mail_host = email_domain(owner_email)
        site_host = site_domain(company.website)

        corporate = mail_host is not None and mail_host not in PUBLIC_MAIL_DOMAINS
        checks.append(
            Check(
                "corporate_email",
                corporate,
                "Почта аккаунта на корпоративном домене"
                if corporate
                else "Почта аккаунта на публичном сервисе — войдите с "
                "корпоративной почты или дождитесь модератора",
            )
        )
        if site_host is None:
            checks.append(
                Check("email_matches_website", False, "Не указан сайт компании")
            )
        else:
            matches = corporate and same_organization_domain(mail_host or "", site_host)
            checks.append(
                Check(
                    "email_matches_website",
                    matches,
                    f"Домен почты совпадает с сайтом {site_host}"
                    if matches
                    else f"Домен почты не совпадает с сайтом {site_host}",
                )
            )
        if company.website and company.inn:
            found = await self.website.mentions(company.website, company.inn)
            checks.append(
                Check(
                    "website_mentions_inn",
                    found,
                    {
                        True: "ИНН опубликован на сайте компании",
                        False: "ИНН не найден на сайте (главная, контакты, реквизиты)",
                        None: "Сайт не удалось открыть",
                    }[found],
                )
            )
        else:
            checks.append(
                Check("website_mentions_inn", False, "Не указан сайт компании")
            )
        taken = await self._verified_elsewhere(company.id, company.inn or "")
        checks.append(
            Check(
                "inn_unique",
                not taken,
                "ИНН подтверждён только за вами"
                if not taken
                else "Этот ИНН уже подтверждён за другим работодателем",
            )
        )
        return checks

    async def _verified_elsewhere(self, company_id: uuid.UUID, inn: str) -> bool:
        other = await self.session.scalar(
            select(Company.id).where(
                Company.inn == inn,
                Company.id != company_id,
                Company.verification_status == VerificationStatus.VERIFIED,
            )
        )
        return other is not None
