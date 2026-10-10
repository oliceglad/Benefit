"""Подборка кандидатов: критерии из потребности или вакансии + отметки
работодателя + история контактов → matching-service.

Правила пересчёта подборки по вакансии (сохранённый снимок):

1. Изменились требования (навыки, грейд, специализация, зарплата, формат,
   город, описание, обязанности, настройки подбора, отрасль компании) —
   ``matching_version`` растёт, подборка пересчитывается при следующем
   запросе, в ответе — кто добавился и кто выпал.
2. Изменились отметки «подходит / не подходит» — пересчёт без смены версии.
3. База кандидатов меняется постоянно — снимок живёт
   ``match_snapshot_ttl_minutes``; ``refresh=true`` пересчитывает сразу.
4. Контакты (приглашён, отказался) применяются при каждом чтении.
5. Статус и даты вакансии на подбор не влияют.
"""

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from benefit_common.errors import AppError, ConflictError
from benefit_common.internal import InternalClient, raise_for_client_error
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    FeedbackVerdict,
    HiringNeed,
    NeedFeedback,
    Vacancy,
    VacancyMatchSnapshot,
    VacancyStatus,
)

logger = logging.getLogger(__name__)


class Matcher(Protocol):
    async def match(self, criteria: dict[str, Any]) -> dict[str, Any]: ...


class ContactDirectory(Protocol):
    async def contacts(self, employer_id: uuid.UUID) -> dict[str, str]:
        """С кем уже был контакт: ``{candidate_id: статус}``."""
        ...


def need_criteria(
    need: HiringNeed,
    feedback: list[NeedFeedback] | None = None,
    contacted: dict[str, str] | None = None,
) -> dict[str, Any]:
    feedback = feedback or []
    return {
        "specialization": need.specialization,
        "grade": need.grade,
        "required_skills": need.required_skills,
        "optional_skills": need.optional_skills,
        "title": need.title,
        "team_description": need.team_description,
        "industry": need.company.industry,
        "work_formats": need.work_formats,
        "city": need.city,
        "salary_to": need.salary_to,
        "currency": need.currency,
        "require_confirmed_grade": need.require_confirmed_grade,
        "strict_skills": need.strict_skills,
        "grade_tolerance": need.grade_tolerance,
        "min_experience_months": need.min_experience_months,
        "hard_budget": need.hard_budget,
        "strict_format": need.strict_format,
        "liked_ids": [
            str(f.candidate_id) for f in feedback if f.verdict == FeedbackVerdict.LIKE
        ],
        "disliked_ids": [
            str(f.candidate_id)
            for f in feedback
            if f.verdict == FeedbackVerdict.DISLIKE
        ],
        "contacted": contacted or {},
    }


# Сколько лучших кандидатов хранится в снимке подборки вакансии.
SNAPSHOT_SIZE = 100
# Ключи критериев, не относящиеся к требованиям вакансии.
VOLATILE_KEYS = {"liked_ids", "disliked_ids", "contacted"}


def _feedback_ids(feedback: list[NeedFeedback]) -> dict[str, list[str]]:
    return {
        "liked_ids": sorted(
            str(f.candidate_id) for f in feedback if f.verdict == FeedbackVerdict.LIKE
        ),
        "disliked_ids": sorted(
            str(f.candidate_id)
            for f in feedback
            if f.verdict == FeedbackVerdict.DISLIKE
        ),
    }


def vacancy_criteria(
    vacancy: Vacancy, feedback: list[NeedFeedback] | None = None
) -> dict[str, Any]:
    """Критерии подбора из вакансии (компания должна быть загружена)."""
    from app.schemas.employer import MatchingSettings

    text = "\n".join([vacancy.description, *vacancy.responsibilities])
    return {
        "specialization": vacancy.specialization,
        "grade": vacancy.grade,
        "required_skills": vacancy.required_skills,
        "optional_skills": vacancy.optional_skills,
        "title": vacancy.title,
        # Описание и обязанности — ключевые слова для близости опыта.
        "team_description": text,
        "industry": vacancy.company.industry,
        "work_formats": [vacancy.work_format] if vacancy.work_format else [],
        "city": vacancy.city,
        "salary_to": vacancy.salary_to,
        "currency": vacancy.currency,
        **MatchingSettings(**vacancy.matching).model_dump(),
        **_feedback_ids(feedback or []),
        "contacted": {},
    }


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def criteria_hash(criteria: dict[str, Any]) -> str:
    """Отпечаток требований: меняется только при изменении того, что влияет
    на отбор и ранжирование."""
    return _digest({k: v for k, v in criteria.items() if k not in VOLATILE_KEYS})


def feedback_hash(criteria: dict[str, Any]) -> str:
    return _digest([criteria["liked_ids"], criteria["disliked_ids"]])


def _candidate_id(item: dict[str, Any]) -> str:
    return str(item["candidate"]["user_id"])


def apply_contacts(
    result: dict[str, Any], contacts: dict[str, str], hide_contacted: bool
) -> tuple[list[dict[str, Any]], int]:
    """Свежие контакты поверх сохранённой подборки.

    Отказавшиеся от приглашения и отклонённые по отклику не показываются
    (как в matching-service); ``hide_contacted`` скрывает всех, с кем был
    контакт. Возвращает кандидатов и сколько из них убрано.
    """
    kept, removed = [], 0
    for item in result["candidates"]:
        status = contacts.get(_candidate_id(item))
        if status and (
            status.endswith(":declined")
            or status == "application:rejected"
            or hide_contacted
        ):
            removed += 1
            continue
        kept.append({**item, "contact_status": status})
    return kept, removed


class VacancyMatcher:
    """Подборка по вакансии с сохранением и правилами пересчёта."""

    def __init__(
        self, session: AsyncSession, matcher: "Matcher", contacts: "ContactDirectory"
    ) -> None:
        self.session = session
        self.matcher = matcher
        self.contacts = contacts

    async def feedback(self, vacancy_id: uuid.UUID) -> list[NeedFeedback]:
        return list(
            await self.session.scalars(
                select(NeedFeedback)
                .where(NeedFeedback.vacancy_id == vacancy_id)
                .order_by(NeedFeedback.updated_at.desc())
            )
        )

    async def matches(
        self,
        vacancy: Vacancy,
        *,
        limit: int,
        offset: int,
        hide_contacted: bool,
        refresh: bool,
    ) -> dict[str, Any]:
        if vacancy.status == VacancyStatus.ARCHIVED:
            raise ConflictError(
                "Вакансия в архиве: подбор недоступен", code="vacancy_archived"
            )
        criteria = vacancy_criteria(vacancy, await self.feedback(vacancy.id))
        requirements, preferences = criteria_hash(criteria), feedback_hash(criteria)
        contacts = await self.contacts.contacts(vacancy.owner_id)
        snapshot = await self.session.get(VacancyMatchSnapshot, vacancy.id)

        reason = self._reason(snapshot, requirements, preferences, refresh)
        if (
            reason == "criteria"
            and snapshot
            and snapshot.version == vacancy.matching_version
        ):
            # Требования изменились не через вакансию (например, отрасль
            # компании) — версия всё равно растёт.
            vacancy.matching_version += 1
        if reason is not None:
            snapshot = await self._recompute(
                vacancy, snapshot, criteria, contacts, requirements, preferences, reason
            )
        assert snapshot is not None

        candidates, removed = apply_contacts(snapshot.result, contacts, hide_contacted)
        result = snapshot.result
        return {
            "vacancy_id": vacancy.id,
            "matching_version": snapshot.version,
            "computed_at": snapshot.computed_at,
            "recalculated": reason,
            "changes": snapshot.changes,
            "total": max(result["total"] - removed, len(candidates)),
            "categories": result["categories"],
            "candidates": candidates[offset : offset + limit],
            "excluded": result["excluded"],
            "suggestions": result["suggestions"],
            "keywords": result["keywords"],
        }

    @staticmethod
    def _reason(
        snapshot: VacancyMatchSnapshot | None,
        requirements: str,
        preferences: str,
        refresh: bool,
    ) -> str | None:
        if snapshot is None:
            return "initial"
        if snapshot.criteria_hash != requirements:
            return "criteria"
        if snapshot.feedback_hash != preferences:
            return "feedback"
        if refresh:
            return "refresh"
        ttl = timedelta(minutes=settings.match_snapshot_ttl_minutes)
        if datetime.now(UTC) - snapshot.computed_at > ttl:
            return "expired"
        return None

    async def _recompute(
        self,
        vacancy: Vacancy,
        snapshot: VacancyMatchSnapshot | None,
        criteria: dict[str, Any],
        contacts: dict[str, str],
        requirements: str,
        preferences: str,
        reason: str,
    ) -> VacancyMatchSnapshot:
        result = await self.matcher.match(
            criteria
            | {
                "contacted": contacts,
                "limit": SNAPSHOT_SIZE,
                "offset": 0,
                "hide_contacted": False,
            }
        )
        changes = None
        if snapshot is not None and reason == "criteria":
            old = [_candidate_id(c) for c in snapshot.result["candidates"]]
            new = [_candidate_id(c) for c in result["candidates"]]
            changes = {
                "from_version": snapshot.version,
                "to_version": vacancy.matching_version,
                "added": [c for c in new if c not in set(old)],
                "removed": [c for c in old if c not in set(new)],
            }
        elif snapshot is not None and snapshot.version == vacancy.matching_version:
            # Пересчёт без смены требований: разница с прошлой версией остаётся.
            changes = snapshot.changes
        if snapshot is None:
            snapshot = VacancyMatchSnapshot(vacancy_id=vacancy.id)
            self.session.add(snapshot)
        snapshot.version = vacancy.matching_version
        snapshot.criteria_hash = requirements
        snapshot.feedback_hash = preferences
        snapshot.reason = reason
        snapshot.computed_at = datetime.now(UTC)
        snapshot.result = result
        snapshot.changes = changes
        await self.session.commit()
        logger.info("Vacancy %s matches recalculated (%s)", vacancy.id, reason)
        return snapshot


class MatchingClient:
    def __init__(self) -> None:
        self.client = InternalClient(settings.matching_service_url, service="matching")

    async def match(self, criteria: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.post("/internal/v1/match", json=criteria)
        raise_for_client_error(response)
        return response.json()


class ApplicationsClient:
    def __init__(self) -> None:
        self.client = InternalClient(
            settings.applications_service_url, service="applications"
        )

    async def contacts(self, employer_id: uuid.UUID) -> dict[str, str]:
        try:
            response = await self.client.get(
                f"/internal/v1/employers/{employer_id}/contacts"
            )
            raise_for_client_error(response)
        except AppError:
            # Подборка полезна и без пометок о контактах.
            logger.warning("Contacts unavailable, matching without them")
            return {}
        return response.json()


def get_matcher() -> Matcher:
    return MatchingClient()


def get_contacts() -> ContactDirectory:
    return ApplicationsClient()
