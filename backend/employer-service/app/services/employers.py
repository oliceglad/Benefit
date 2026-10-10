"""Профиль компании, потребности и вакансии работодателя."""

import uuid
from datetime import UTC, datetime
from typing import Any

from benefit_common.errors import AppError, ConflictError, NotFoundError
from benefit_common.security import Principal
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Company,
    HiringNeed,
    NeedFeedback,
    NeedStatus,
    Vacancy,
    VacancyStatus,
)
from app.schemas.employer import CompanyIn, MatchingSettings, NeedIn, VacancyIn
from app.services.matching import criteria_hash, vacancy_criteria
from app.services.verification import reset_verification


def _company_required() -> ConflictError:
    return ConflictError("Сначала заполните профиль компании", code="company_required")


# Допустимые переходы статуса вакансии.
VACANCY_TRANSITIONS: dict[VacancyStatus, set[VacancyStatus]] = {
    VacancyStatus.DRAFT: {VacancyStatus.PUBLISHED, VacancyStatus.ARCHIVED},
    VacancyStatus.PUBLISHED: {
        VacancyStatus.DRAFT,
        VacancyStatus.CLOSED,
        VacancyStatus.ARCHIVED,
    },
    VacancyStatus.CLOSED: {VacancyStatus.PUBLISHED, VacancyStatus.ARCHIVED},
    # Из архива — только восстановление в черновик.
    VacancyStatus.ARCHIVED: {VacancyStatus.DRAFT},
}
BLOCKER_TITLES = {
    "required_skills": "обязательные навыки",
    "responsibilities": "обязанности",
}


def _ensure_publishable(vacancy: Vacancy) -> None:
    blockers = vacancy.publish_blockers
    if blockers:
        raise AppError(
            "Для публикации заполните: "
            + ", ".join(BLOCKER_TITLES[b] for b in blockers),
            code="vacancy_incomplete",
            status_code=422,
            details=[
                {"field": b, "message": "Обязательно для публикации"} for b in blockers
            ],
        )


class EmployerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Компания ---

    async def company_of(self, owner_id: uuid.UUID) -> Company | None:
        return await self.session.scalar(
            select(Company).where(Company.owner_id == owner_id)
        )

    async def my_company(self, employer: Principal) -> Company:
        company = await self.company_of(employer.id)
        if company is None:
            raise NotFoundError(
                "Профиль компании не заполнен", code="company_not_found"
            )
        return company

    async def save_company(self, employer: Principal, data: CompanyIn) -> Company:
        company = await self.company_of(employer.id)
        if company is None:
            company = Company(owner_id=employer.id)
            self.session.add(company)
        basis = (company.inn, company.website)
        for field, value in data.model_dump(mode="json").items():
            setattr(company, field, value)
        if (company.inn, company.website) != basis:
            # Проверка основана на ИНН и сайте: при их смене её нужно пройти
            # заново, иначе можно подменить компанию после подтверждения.
            reset_verification(company)
        elif company.registry_data:
            # Юридическое наименование — только из реестра.
            company.legal_name = company.registry_data["full_name"][:300]
        await self.session.commit()
        await self.session.refresh(company)
        return company

    async def company(self, company_id: uuid.UUID) -> Company:
        company = await self.session.get(Company, company_id)
        if company is None:
            raise NotFoundError("Компания не найдена", code="company_not_found")
        return company

    # --- Потребности ---

    async def needs(self, employer: Principal) -> list[HiringNeed]:
        result = await self.session.scalars(
            select(HiringNeed)
            .where(HiringNeed.owner_id == employer.id)
            .options(selectinload(HiringNeed.company))
            .order_by(HiringNeed.created_at.desc())
        )
        return list(result)

    async def need(self, employer: Principal, need_id: uuid.UUID) -> HiringNeed:
        need = await self.session.scalar(
            select(HiringNeed)
            .where(HiringNeed.id == need_id)
            .options(selectinload(HiringNeed.company))
        )
        if need is None or need.owner_id != employer.id:
            raise NotFoundError("Потребность не найдена", code="need_not_found")
        return need

    async def save_need(
        self, employer: Principal, data: NeedIn, need_id: uuid.UUID | None = None
    ) -> HiringNeed:
        if need_id is None:
            company = await self.company_of(employer.id)
            if company is None:
                raise _company_required()
            need = HiringNeed(owner_id=employer.id, company_id=company.id)
            self.session.add(need)
        else:
            need = await self.need(employer, need_id)
        for field, value in data.model_dump(mode="json").items():
            setattr(need, field, value)
        await self.session.commit()
        return await self.need(employer, need.id)

    async def set_need_status(
        self, employer: Principal, need_id: uuid.UUID, status: NeedStatus
    ) -> HiringNeed:
        need = await self.need(employer, need_id)
        need.status = status
        await self.session.commit()
        return await self.need(employer, need.id)

    # --- Отметки по кандидатам ---

    async def feedback(
        self, employer: Principal, need_id: uuid.UUID
    ) -> list[NeedFeedback]:
        await self.need(employer, need_id)
        result = await self.session.scalars(
            select(NeedFeedback)
            .where(NeedFeedback.need_id == need_id)
            .order_by(NeedFeedback.updated_at.desc())
        )
        return list(result)

    async def set_feedback(
        self,
        employer: Principal,
        need_id: uuid.UUID,
        candidate_id: uuid.UUID,
        verdict: str,
        comment: str | None,
    ) -> NeedFeedback:
        await self.need(employer, need_id)
        item = await self.session.scalar(
            select(NeedFeedback).where(
                NeedFeedback.need_id == need_id,
                NeedFeedback.candidate_id == candidate_id,
            )
        )
        if item is None:
            item = NeedFeedback(need_id=need_id, candidate_id=candidate_id)
            self.session.add(item)
        item.verdict = verdict
        item.comment = comment
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete_feedback(
        self, employer: Principal, need_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> None:
        await self.need(employer, need_id)
        item = await self.session.scalar(
            select(NeedFeedback).where(
                NeedFeedback.need_id == need_id,
                NeedFeedback.candidate_id == candidate_id,
            )
        )
        if item is not None:
            await self.session.delete(item)
            await self.session.commit()

    async def set_vacancy_feedback(
        self,
        employer: Principal,
        vacancy_id: uuid.UUID,
        candidate_id: uuid.UUID,
        verdict: str,
        comment: str | None,
    ) -> NeedFeedback:
        """Отметка в подборке вакансии (меняет ранжирование при пересчёте)."""
        await self.my_vacancy(employer, vacancy_id)
        item = await self.session.scalar(
            select(NeedFeedback).where(
                NeedFeedback.vacancy_id == vacancy_id,
                NeedFeedback.candidate_id == candidate_id,
            )
        )
        if item is None:
            item = NeedFeedback(vacancy_id=vacancy_id, candidate_id=candidate_id)
            self.session.add(item)
        item.verdict = verdict
        item.comment = comment
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete_vacancy_feedback(
        self, employer: Principal, vacancy_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> None:
        await self.my_vacancy(employer, vacancy_id)
        item = await self.session.scalar(
            select(NeedFeedback).where(
                NeedFeedback.vacancy_id == vacancy_id,
                NeedFeedback.candidate_id == candidate_id,
            )
        )
        if item is not None:
            await self.session.delete(item)
            await self.session.commit()

    # --- Вакансии ---

    async def my_vacancies(
        self, employer: Principal, status: VacancyStatus | None = None
    ) -> list[Vacancy]:
        """Вакансии работодателя; без фильтра — все, кроме архивных."""
        query = select(Vacancy).where(Vacancy.owner_id == employer.id)
        if status is None:
            query = query.where(Vacancy.status != VacancyStatus.ARCHIVED)
        else:
            query = query.where(Vacancy.status == status)
        result = await self.session.scalars(
            query.options(selectinload(Vacancy.company)).order_by(
                Vacancy.created_at.desc()
            )
        )
        return list(result)

    async def vacancy_by_id(self, vacancy_id: uuid.UUID) -> Vacancy | None:
        return await self.session.scalar(
            select(Vacancy)
            .where(Vacancy.id == vacancy_id)
            .options(selectinload(Vacancy.company))
        )

    async def my_vacancy(self, employer: Principal, vacancy_id: uuid.UUID) -> Vacancy:
        vacancy = await self.vacancy_by_id(vacancy_id)
        if vacancy is None or vacancy.owner_id != employer.id:
            raise NotFoundError("Вакансия не найдена", code="vacancy_not_found")
        return vacancy

    async def save_vacancy(
        self, employer: Principal, data: VacancyIn, vacancy_id: uuid.UUID | None = None
    ) -> Vacancy:
        need = await self.need(employer, data.need_id) if data.need_id else None
        values = data.model_dump(mode="json", exclude={"matching"})
        if vacancy_id is None:
            company = await self.company_of(employer.id)
            if company is None:
                raise _company_required()
            vacancy = Vacancy(owner_id=employer.id, company_id=company.id)
            vacancy.company = company
            self.session.add(vacancy)
            before = None
            if need is not None:
                values, settings = self._inherit_from_need(need, data, values)
            else:
                settings = (data.matching or MatchingSettings()).model_dump()
        else:
            vacancy = await self.my_vacancy(employer, vacancy_id)
            if vacancy.status == VacancyStatus.ARCHIVED:
                raise ConflictError(
                    "Вакансия в архиве: восстановите её, чтобы изменить",
                    code="vacancy_archived",
                )
            before = criteria_hash(vacancy_criteria(vacancy))
            # Не переданы — прежние настройки подбора.
            settings = data.matching.model_dump() if data.matching else vacancy.matching
        for field, value in values.items():
            setattr(vacancy, field, value)
        vacancy.matching_settings = settings
        if vacancy.status == VacancyStatus.PUBLISHED:
            # Опубликованная вакансия должна оставаться полной.
            _ensure_publishable(vacancy)
        if before is not None and criteria_hash(vacancy_criteria(vacancy)) != before:
            # Требования изменились — сохранённая подборка устарела и будет
            # пересчитана при следующем запросе.
            vacancy.matching_version += 1
        await self.session.flush()
        if vacancy_id is None and need is not None:
            await self._copy_feedback(need.id, vacancy.id)
        await self.session.commit()
        return await self.my_vacancy(employer, vacancy.id)

    @staticmethod
    def _inherit_from_need(
        need: HiringNeed, data: VacancyIn, values: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Вакансия из потребности: пустые навыки и настройки подбора
        берутся из неё (один раз — дальше у вакансии свои критерии)."""
        if not data.required_skills and not data.optional_skills:
            values["required_skills"] = list(need.required_skills)
            values["optional_skills"] = list(need.optional_skills)
        if data.matching is not None:
            return values, data.matching.model_dump()
        settings = MatchingSettings(
            **{field: getattr(need, field) for field in MatchingSettings.model_fields}
        )
        return values, settings.model_dump()

    async def _copy_feedback(self, need_id: uuid.UUID, vacancy_id: uuid.UUID) -> None:
        """Отметки по кандидатам, сделанные в подборке потребности."""
        for item in await self.session.scalars(
            select(NeedFeedback).where(NeedFeedback.need_id == need_id)
        ):
            self.session.add(
                NeedFeedback(
                    vacancy_id=vacancy_id,
                    candidate_id=item.candidate_id,
                    verdict=item.verdict,
                    comment=item.comment,
                )
            )

    async def set_vacancy_status(
        self, employer: Principal, vacancy_id: uuid.UUID, status: VacancyStatus
    ) -> Vacancy:
        vacancy = await self.my_vacancy(employer, vacancy_id)
        current = VacancyStatus(vacancy.status)
        if status == current:
            return vacancy
        if status not in VACANCY_TRANSITIONS[current]:
            raise ConflictError(
                "Такой переход статуса невозможен"
                + (
                    ": восстановите вакансию из архива в черновик"
                    if current == VacancyStatus.ARCHIVED
                    else ""
                ),
                code=f"vacancy_{current}",
            )
        now = datetime.now(UTC)
        if status == VacancyStatus.PUBLISHED:
            _ensure_publishable(vacancy)
            vacancy.published_at = vacancy.published_at or now
            vacancy.closed_at = None
        elif status == VacancyStatus.CLOSED:
            vacancy.closed_at = now
        elif status == VacancyStatus.ARCHIVED:
            vacancy.archived_at = now
        if current == VacancyStatus.ARCHIVED:
            vacancy.archived_at = None
        vacancy.status = status
        await self.session.commit()
        return await self.my_vacancy(employer, vacancy.id)

    async def published_vacancy(self, vacancy_id: uuid.UUID) -> Vacancy:
        vacancy = await self.vacancy_by_id(vacancy_id)
        if vacancy is None or vacancy.status != VacancyStatus.PUBLISHED:
            raise NotFoundError("Вакансия не найдена", code="vacancy_not_found")
        return vacancy

    async def search_vacancies(
        self,
        *,
        specialization: str | None,
        grade: str | None,
        skill: str | None,
        q: str | None,
        salary_min: int | None,
        salary_type: str | None,
        work_format: str | None,
        city: str | None,
        company_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[int, list[Vacancy]]:
        """Опубликованные вакансии для кандидатов."""
        query: Select[Any] = select(Vacancy).where(
            Vacancy.status == VacancyStatus.PUBLISHED
        )
        if specialization:
            query = query.where(Vacancy.specialization == specialization)
        if grade:
            query = query.where(Vacancy.grade == grade)
        if skill:
            query = query.where(
                or_(
                    Vacancy.required_skills.contains([skill]),
                    Vacancy.optional_skills.contains([skill]),
                )
            )
        if q:
            # %, _ и \ в запросе — обычные символы, а не шаблон LIKE.
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            query = query.where(
                or_(
                    Vacancy.title.ilike(pattern, escape="\\"),
                    Vacancy.description.ilike(pattern, escape="\\"),
                )
            )
        if salary_min:
            # Подходят вакансии, где верхняя граница не ниже ожиданий.
            query = query.where(
                or_(Vacancy.salary_to.is_(None), Vacancy.salary_to >= salary_min)
            )
        if salary_type:
            query = query.where(Vacancy.salary_type == salary_type)
        if work_format:
            query = query.where(Vacancy.work_format == work_format)
        if city:
            query = query.where(func.lower(Vacancy.city) == city.lower())
        if company_id:
            query = query.where(Vacancy.company_id == company_id)
        total = await self.session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        items = await self.session.scalars(
            query.options(selectinload(Vacancy.company))
            .order_by(Vacancy.published_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return total or 0, list(items)
