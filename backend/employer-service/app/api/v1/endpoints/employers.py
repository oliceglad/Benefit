"""Кабинет работодателя: профиль компании, потребности, вакансии."""

import uuid
from typing import Annotated

from benefit_common.security import CurrentPrincipal, Employer
from fastapi import APIRouter, Query, status

from app.api.deps import ContactsDep, EmployerServiceDep, MatcherDep
from app.schemas.employer import (
    CompanyIn,
    CompanyResponse,
    FeedbackIn,
    FeedbackResponse,
    MatchResponse,
    NeedIn,
    NeedResponse,
    NeedStatusUpdate,
    VacancyIn,
    VacancyResponse,
    VacancyStatusUpdate,
)
from app.services.matching import need_criteria

router = APIRouter()


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


# --- Профиль компании ---


@router.get("/company", response_model=CompanyResponse, tags=["компания"])
async def my_company(
    employer: Employer, service: EmployerServiceDep
) -> CompanyResponse:
    return CompanyResponse.model_validate(await service.my_company(employer))


@router.put("/company", response_model=CompanyResponse, tags=["компания"])
async def save_company(
    data: CompanyIn, employer: Employer, service: EmployerServiceDep
) -> CompanyResponse:
    """Создать или обновить профиль компании: описание, направление, контакты."""
    return CompanyResponse.model_validate(await service.save_company(employer, data))


@router.get(
    "/companies/{company_id}", response_model=CompanyResponse, tags=["компания"]
)
async def company(
    company_id: uuid.UUID, _: CurrentPrincipal, service: EmployerServiceDep
) -> CompanyResponse:
    """Профиль компании для кандидатов (например, из приглашения)."""
    return CompanyResponse.model_validate(await service.company(company_id))


# --- Потребности и подборка ---


@router.get("/needs", response_model=list[NeedResponse], tags=["потребности"])
async def list_needs(employer: Employer, service: EmployerServiceDep) -> list:
    return [NeedResponse.model_validate(n) for n in await service.needs(employer)]


@router.post(
    "/needs",
    response_model=NeedResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["потребности"],
)
async def create_need(
    data: NeedIn, employer: Employer, service: EmployerServiceDep
) -> NeedResponse:
    """Кого ищем: специализация, грейд, стек, чем занимается команда."""
    return NeedResponse.model_validate(await service.save_need(employer, data))


@router.get("/needs/{need_id}", response_model=NeedResponse, tags=["потребности"])
async def get_need(
    need_id: uuid.UUID, employer: Employer, service: EmployerServiceDep
) -> NeedResponse:
    return NeedResponse.model_validate(await service.need(employer, need_id))


@router.put("/needs/{need_id}", response_model=NeedResponse, tags=["потребности"])
async def update_need(
    need_id: uuid.UUID, data: NeedIn, employer: Employer, service: EmployerServiceDep
) -> NeedResponse:
    return NeedResponse.model_validate(await service.save_need(employer, data, need_id))


@router.patch("/needs/{need_id}", response_model=NeedResponse, tags=["потребности"])
async def set_need_status(
    need_id: uuid.UUID,
    data: NeedStatusUpdate,
    employer: Employer,
    service: EmployerServiceDep,
) -> NeedResponse:
    return NeedResponse.model_validate(
        await service.set_need_status(employer, need_id, data.status)
    )


@router.get(
    "/needs/{need_id}/matches", response_model=MatchResponse, tags=["потребности"]
)
async def matches(
    need_id: uuid.UUID,
    employer: Employer,
    service: EmployerServiceDep,
    matcher: MatcherDep,
    contacts: ContactsDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    hide_contacted: Annotated[
        bool, Query(description="Скрыть кандидатов, с которыми уже был контакт")
    ] = False,
) -> MatchResponse:
    """Подборка кандидатов: рекомендованные категории и кандидаты
    с обоснованием (почему кандидат попал в подборку)."""
    need = await service.need(employer, need_id)
    criteria = need_criteria(
        need,
        await service.feedback(employer, need_id),
        await contacts.contacts(employer.id),
    )
    result = await matcher.match(
        criteria | {"limit": limit, "offset": offset, "hide_contacted": hide_contacted}
    )
    return MatchResponse(need_id=need.id, **result)


@router.get(
    "/needs/{need_id}/feedback",
    response_model=list[FeedbackResponse],
    tags=["потребности"],
)
async def list_feedback(
    need_id: uuid.UUID, employer: Employer, service: EmployerServiceDep
) -> list:
    return [
        FeedbackResponse.model_validate(f)
        for f in await service.feedback(employer, need_id)
    ]


@router.put(
    "/needs/{need_id}/feedback/{candidate_id}",
    response_model=FeedbackResponse,
    tags=["потребности"],
)
async def set_feedback(
    need_id: uuid.UUID,
    candidate_id: uuid.UUID,
    data: FeedbackIn,
    employer: Employer,
    service: EmployerServiceDep,
) -> FeedbackResponse:
    """«Подходит» поднимает похожих кандидатов в подборке, «не подходит»
    убирает кандидата и опускает похожих на него."""
    return FeedbackResponse.model_validate(
        await service.set_feedback(
            employer, need_id, candidate_id, data.verdict, data.comment
        )
    )


@router.delete(
    "/needs/{need_id}/feedback/{candidate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["потребности"],
)
async def delete_feedback(
    need_id: uuid.UUID,
    candidate_id: uuid.UUID,
    employer: Employer,
    service: EmployerServiceDep,
) -> None:
    await service.delete_feedback(employer, need_id, candidate_id)


# --- Вакансии (управление) ---


@router.get("/vacancies", response_model=list[VacancyResponse], tags=["вакансии"])
async def my_vacancies(employer: Employer, service: EmployerServiceDep) -> list:
    return [
        VacancyResponse.model_validate(v) for v in await service.my_vacancies(employer)
    ]


@router.post(
    "/vacancies",
    response_model=VacancyResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["вакансии"],
)
async def create_vacancy(
    data: VacancyIn, employer: Employer, service: EmployerServiceDep
) -> VacancyResponse:
    """Черновик вакансии; публикация — ``PATCH {status: "published"}``."""
    return VacancyResponse.model_validate(await service.save_vacancy(employer, data))


@router.get(
    "/vacancies/{vacancy_id}", response_model=VacancyResponse, tags=["вакансии"]
)
async def get_my_vacancy(
    vacancy_id: uuid.UUID, employer: Employer, service: EmployerServiceDep
) -> VacancyResponse:
    return VacancyResponse.model_validate(
        await service.my_vacancy(employer, vacancy_id)
    )


@router.put(
    "/vacancies/{vacancy_id}", response_model=VacancyResponse, tags=["вакансии"]
)
async def update_vacancy(
    vacancy_id: uuid.UUID,
    data: VacancyIn,
    employer: Employer,
    service: EmployerServiceDep,
) -> VacancyResponse:
    return VacancyResponse.model_validate(
        await service.save_vacancy(employer, data, vacancy_id)
    )


@router.patch(
    "/vacancies/{vacancy_id}", response_model=VacancyResponse, tags=["вакансии"]
)
async def set_vacancy_status(
    vacancy_id: uuid.UUID,
    data: VacancyStatusUpdate,
    employer: Employer,
    service: EmployerServiceDep,
) -> VacancyResponse:
    """Опубликовать, снять в черновик или закрыть вакансию."""
    return VacancyResponse.model_validate(
        await service.set_vacancy_status(employer, vacancy_id, data.status)
    )
