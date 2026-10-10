"""Внутренний API: вакансии и компании (для applications-service), удаление
данных пользователя (от auth-service)."""

import uuid

from benefit_common.errors import NotFoundError
from benefit_common.internal import verify_internal_token
from fastapi import APIRouter, Depends, status
from sqlalchemy import delete

from app.api.deps import EmployerServiceDep, SessionDep
from app.models import Company, NeedFeedback
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


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, session: SessionDep) -> None:
    """Аккаунт удалён: компания работодателя со всеми потребностями и
    вакансиями (каскадом), а также отметки работодателей по удалённому
    кандидату. Идемпотентно."""
    await session.execute(delete(Company).where(Company.owner_id == user_id))
    await session.execute(
        delete(NeedFeedback).where(NeedFeedback.candidate_id == user_id)
    )
    await session.commit()
