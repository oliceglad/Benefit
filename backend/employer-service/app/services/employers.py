"""Профиль компании, потребности и вакансии работодателя."""

import uuid
from datetime import UTC, datetime
from typing import Any

from benefit_common.errors import ConflictError, NotFoundError
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
from app.schemas.employer import CompanyIn, NeedIn, VacancyIn


def _company_required() -> ConflictError:
    return ConflictError("Сначала заполните профиль компании", code="company_required")


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
        for field, value in data.model_dump(mode="json").items():
            setattr(company, field, value)
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

    # --- Вакансии ---

    async def my_vacancies(self, employer: Principal) -> list[Vacancy]:
        result = await self.session.scalars(
            select(Vacancy)
            .where(Vacancy.owner_id == employer.id)
            .options(selectinload(Vacancy.company))
            .order_by(Vacancy.created_at.desc())
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
        if data.need_id is not None:
            await self.need(employer, data.need_id)
        if vacancy_id is None:
            company = await self.company_of(employer.id)
            if company is None:
                raise _company_required()
            vacancy = Vacancy(owner_id=employer.id, company_id=company.id)
            self.session.add(vacancy)
        else:
            vacancy = await self.my_vacancy(employer, vacancy_id)
        for field, value in data.model_dump(mode="json").items():
            setattr(vacancy, field, value)
        await self.session.commit()
        return await self.my_vacancy(employer, vacancy.id)

    async def set_vacancy_status(
        self, employer: Principal, vacancy_id: uuid.UUID, status: VacancyStatus
    ) -> Vacancy:
        vacancy = await self.my_vacancy(employer, vacancy_id)
        if status == VacancyStatus.PUBLISHED and vacancy.published_at is None:
            vacancy.published_at = datetime.now(UTC)
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
            query = query.where(Vacancy.skills.contains([skill]))
        if q:
            pattern = f"%{q}%"
            query = query.where(
                or_(Vacancy.title.ilike(pattern), Vacancy.description.ilike(pattern))
            )
        if salary_min:
            # Подходят вакансии, где верхняя граница не ниже ожиданий.
            query = query.where(
                or_(Vacancy.salary_to.is_(None), Vacancy.salary_to >= salary_min)
            )
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
