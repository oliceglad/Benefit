"""Тесты работодателей: создание, отправка кандидату, прохождение.

Работодатель: ``/employer/tests`` (свои тесты), ``/employer/tests/{id}/assignments``
(отправить кандидату в переписку), ``/employer/assignments`` (результаты).
Кандидат: ``/assignments`` (полученные тесты), ``/assignments/{id}/start`` —
дальше обычный цикл ``/attempts/{id}/current-task`` и ``/answers``.
"""

import uuid
from typing import Annotated

from benefit_common.security import Candidate, Employer
from fastapi import APIRouter, Depends, status

from app.api.deps import AttemptServiceDep, SessionDep
from app.schemas.assessment import AttemptResponse
from app.schemas.content import ActiveUpdate
from app.schemas.employer import (
    AssignmentCreate,
    AssignmentResponse,
    EmployerAssignmentResponse,
    EmployerTestDetail,
    EmployerTestIn,
    EmployerTestSummary,
)
from app.services.employer_tests import (
    ChatDirectory,
    EmployerTestService,
    get_chat_directory,
)

router = APIRouter(tags=["assessments: тесты работодателей"])


def get_service(
    session: SessionDep,
    attempts: AttemptServiceDep,
    chat: Annotated[ChatDirectory, Depends(get_chat_directory)],
) -> EmployerTestService:
    return EmployerTestService(session, chat, attempts)


ServiceDep = Annotated[EmployerTestService, Depends(get_service)]


# --- Работодатель ------------------------------------------------------------


@router.get("/employer/tests", response_model=list[EmployerTestSummary])
async def list_tests(employer: Employer, service: ServiceDep) -> list:
    return await service.list_tests(employer)


@router.post(
    "/employer/tests",
    response_model=EmployerTestDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_test(
    data: EmployerTestIn, employer: Employer, service: ServiceDep
) -> EmployerTestDetail:
    """Свой тест: задачи с вариантами, баллами и лимитом времени."""
    return await service.create_test(employer, data)


@router.get("/employer/tests/{test_id}", response_model=EmployerTestDetail)
async def get_test(
    test_id: uuid.UUID, employer: Employer, service: ServiceDep
) -> EmployerTestDetail:
    return await service.get_test(employer, test_id)


@router.put("/employer/tests/{test_id}", response_model=EmployerTestDetail)
async def replace_test(
    test_id: uuid.UUID, data: EmployerTestIn, employer: Employer, service: ServiceDep
) -> EmployerTestDetail:
    return await service.replace_test(employer, test_id, data)


@router.patch("/employer/tests/{test_id}", response_model=EmployerTestDetail)
async def archive_test(
    test_id: uuid.UUID, data: ActiveUpdate, employer: Employer, service: ServiceDep
) -> EmployerTestDetail:
    """``is_active: false`` — в архив (новым кандидатам не отправить)."""
    return await service.set_active(employer, test_id, data.is_active)


@router.post(
    "/employer/tests/{test_id}/assignments",
    response_model=EmployerAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign(
    test_id: uuid.UUID, data: AssignmentCreate, employer: Employer, service: ServiceDep
) -> EmployerAssignmentResponse:
    """Отправить тест кандидату в переписку (кандидат получит уведомление)."""
    return await service.assign(employer, test_id, data)


@router.get("/employer/assignments", response_model=list[AssignmentResponse])
async def sent_assignments(
    employer: Employer, service: ServiceDep, test_id: uuid.UUID | None = None
) -> list:
    return await service.employer_assignments(employer, test_id)


@router.get(
    "/employer/assignments/{assignment_id}", response_model=EmployerAssignmentResponse
)
async def assignment_result(
    assignment_id: uuid.UUID, employer: Employer, service: ServiceDep
) -> EmployerAssignmentResponse:
    """Результат с ответами кандидата, баллами и временем по каждой задаче."""
    return await service.employer_assignment(employer, assignment_id)


@router.post(
    "/employer/assignments/{assignment_id}/cancel",
    response_model=EmployerAssignmentResponse,
)
async def cancel_assignment(
    assignment_id: uuid.UUID, employer: Employer, service: ServiceDep
) -> EmployerAssignmentResponse:
    return await service.cancel(employer, assignment_id)


# --- Кандидат ------------------------------------------------------------------


@router.get("/assignments", response_model=list[AssignmentResponse])
async def my_assignments(candidate: Candidate, service: ServiceDep) -> list:
    """Тесты, присланные работодателями."""
    return await service.candidate_assignments(candidate)


@router.get("/assignments/{assignment_id}", response_model=AssignmentResponse)
async def my_assignment(
    assignment_id: uuid.UUID, candidate: Candidate, service: ServiceDep
) -> AssignmentResponse:
    return await service.candidate_assignment(candidate, assignment_id)


@router.post("/assignments/{assignment_id}/start", response_model=AttemptResponse)
async def start(
    assignment_id: uuid.UUID, candidate: Candidate, service: ServiceDep
) -> AttemptResponse:
    """Начать тест: дальше ``/attempts/{id}/current-task`` и ``/answers``."""
    return await service.start(candidate, assignment_id)


@router.post("/assignments/{assignment_id}/decline", response_model=AssignmentResponse)
async def decline(
    assignment_id: uuid.UUID, candidate: Candidate, service: ServiceDep
) -> AssignmentResponse:
    return await service.decline(candidate, assignment_id)
