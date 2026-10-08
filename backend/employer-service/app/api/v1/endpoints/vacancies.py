"""Опубликованные вакансии — для кандидатов (``/api/v1/vacancies``)."""

import uuid
from typing import Annotated

from benefit_common.dictionaries import Grade, ITRole, WorkFormat
from benefit_common.security import CurrentPrincipal
from benefit_common.skills import normalize_skill
from fastapi import APIRouter, Query

from app.api.deps import EmployerServiceDep
from app.schemas.employer import VacancyPage, VacancyResponse

router = APIRouter(tags=["вакансии: каталог"])


@router.get("", response_model=VacancyPage)
async def list_vacancies(
    _: CurrentPrincipal,
    service: EmployerServiceDep,
    specialization: ITRole | None = None,
    grade: Grade | None = None,
    skill: Annotated[str | None, Query(max_length=64)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    salary_min: Annotated[int | None, Query(ge=0)] = None,
    work_format: WorkFormat | None = None,
    city: Annotated[str | None, Query(max_length=100)] = None,
    company_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> VacancyPage:
    total, items = await service.search_vacancies(
        specialization=specialization,
        grade=grade,
        skill=normalize_skill(skill) if skill else None,
        q=q,
        salary_min=salary_min,
        work_format=work_format,
        city=city,
        company_id=company_id,
        limit=limit,
        offset=offset,
    )
    return VacancyPage(
        total=total, items=[VacancyResponse.model_validate(v) for v in items]
    )


@router.get("/{vacancy_id}", response_model=VacancyResponse)
async def get_vacancy(
    vacancy_id: uuid.UUID, _: CurrentPrincipal, service: EmployerServiceDep
) -> VacancyResponse:
    return VacancyResponse.model_validate(await service.published_vacancy(vacancy_id))
