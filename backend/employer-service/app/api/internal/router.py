"""Внутренний API для applications-service: вакансии и компании."""

import uuid

from benefit_common.errors import NotFoundError
from benefit_common.internal import verify_internal_token
from fastapi import APIRouter, Depends

from app.api.deps import EmployerServiceDep
from app.schemas.employer import CompanyResponse, VacancyResponse

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)


@router.get("/vacancies/{vacancy_id}", response_model=VacancyResponse)
async def vacancy(
    vacancy_id: uuid.UUID, service: EmployerServiceDep
) -> VacancyResponse:
    """Вакансия в любом статусе (статус проверяет вызывающий)."""
    found = await service.vacancy_by_id(vacancy_id)
    if found is None:
        raise NotFoundError("Вакансия не найдена", code="vacancy_not_found")
    return VacancyResponse.model_validate(found)


@router.get("/companies/by-owner/{owner_id}", response_model=CompanyResponse)
async def company_by_owner(
    owner_id: uuid.UUID, service: EmployerServiceDep
) -> CompanyResponse:
    company = await service.company_of(owner_id)
    if company is None:
        raise NotFoundError("Профиль компании не заполнен", code="company_not_found")
    return CompanyResponse.model_validate(company)
