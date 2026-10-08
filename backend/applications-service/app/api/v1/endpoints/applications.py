"""Отклики на вакансии: кандидат откликается, работодатель отвечает."""

import uuid
from typing import Annotated

from benefit_common.security import Candidate, CurrentPrincipal, Employer
from fastapi import APIRouter, Depends, status

from app.api.deps import SessionDep
from app.models import ApplicationStatus
from app.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationStatusUpdate,
)
from app.services.applications import ApplicationService
from app.services.candidates import CandidateDirectory, get_candidate_directory
from app.services.employers import EmployerDirectory, get_employer_directory

router = APIRouter(tags=["applications: отклики"])


def get_service(
    session: SessionDep,
    candidates: Annotated[CandidateDirectory, Depends(get_candidate_directory)],
    employers: Annotated[EmployerDirectory, Depends(get_employer_directory)],
) -> ApplicationService:
    return ApplicationService(session, candidates, employers)


ServiceDep = Annotated[ApplicationService, Depends(get_service)]


@router.post(
    "", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED
)
async def apply(
    data: ApplicationCreate, candidate: Candidate, service: ServiceDep
) -> ApplicationResponse:
    """Откликнуться на вакансию. Работодатель увидит профиль с контактами."""
    return ApplicationResponse.model_validate(await service.apply(candidate, data))


@router.get("", response_model=list[ApplicationResponse])
async def my_applications(candidate: Candidate, service: ServiceDep) -> list:
    """Мои отклики и их статусы."""
    return [
        ApplicationResponse.model_validate(a) for a in await service.mine(candidate)
    ]


@router.get("/received", response_model=list[ApplicationResponse])
async def received(
    employer: Employer,
    service: ServiceDep,
    vacancy_id: uuid.UUID | None = None,
    status: ApplicationStatus | None = None,
) -> list:
    """Входящие отклики на вакансии работодателя."""
    items = await service.received(employer, vacancy_id, status)
    return [ApplicationResponse.model_validate(a) for a in items]


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: uuid.UUID, principal: CurrentPrincipal, service: ServiceDep
) -> ApplicationResponse:
    return ApplicationResponse.model_validate(
        await service.get(principal, application_id)
    )


@router.post("/{application_id}/withdraw", response_model=ApplicationResponse)
async def withdraw(
    application_id: uuid.UUID, candidate: Candidate, service: ServiceDep
) -> ApplicationResponse:
    return ApplicationResponse.model_validate(
        await service.withdraw(candidate, application_id)
    )


@router.post("/{application_id}/status", response_model=ApplicationResponse)
async def set_status(
    application_id: uuid.UUID,
    data: ApplicationStatusUpdate,
    employer: Employer,
    service: ServiceDep,
) -> ApplicationResponse:
    """Просмотрен, приглашение на собеседование или отказ."""
    return ApplicationResponse.model_validate(
        await service.set_status(employer, application_id, data)
    )
