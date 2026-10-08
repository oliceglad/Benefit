"""Регулярные задания: работодатель выдаёт, кандидат решает, работодатель
оценивает. Результат влияет на актуальность профиля кандидата."""

import uuid

from benefit_common.security import Candidate, CurrentPrincipal, Employer
from fastapi import APIRouter, status

from app.api.deps import TaskServiceDep
from app.models import TaskStatus
from app.schemas.chat import TaskCreate, TaskResponse, TaskReview, TaskSubmit

router = APIRouter(tags=["tasks"])


@router.post(
    "/conversations/{conversation_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    conversation_id: uuid.UUID,
    data: TaskCreate,
    employer: Employer,
    service: TaskServiceDep,
) -> TaskResponse:
    """Выдать задание кандидату в переписке (можно с файлами и повтором)."""
    return TaskResponse.model_validate(
        await service.create(employer, conversation_id, data)
    )


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    principal: CurrentPrincipal,
    service: TaskServiceDep,
    status: TaskStatus | None = None,
    conversation_id: uuid.UUID | None = None,
) -> list[TaskResponse]:
    """Задания пользователя: кандидату — полученные, работодателю — выданные."""
    tasks = await service.list_tasks(principal, status, conversation_id)
    return [TaskResponse.model_validate(t) for t in tasks]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID, principal: CurrentPrincipal, service: TaskServiceDep
) -> TaskResponse:
    return TaskResponse.model_validate(await service.get(principal, task_id))


@router.post("/tasks/{task_id}/submit", response_model=TaskResponse)
async def submit_task(
    task_id: uuid.UUID, data: TaskSubmit, candidate: Candidate, service: TaskServiceDep
) -> TaskResponse:
    """Отправить решение или подход к решению (текст и/или файлы)."""
    return TaskResponse.model_validate(await service.submit(candidate, task_id, data))


@router.post("/tasks/{task_id}/review", response_model=TaskResponse)
async def review_task(
    task_id: uuid.UUID, data: TaskReview, employer: Employer, service: TaskServiceDep
) -> TaskResponse:
    return TaskResponse.model_validate(await service.review(employer, task_id, data))


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    task_id: uuid.UUID, employer: Employer, service: TaskServiceDep
) -> TaskResponse:
    return TaskResponse.model_validate(await service.cancel(employer, task_id))


@router.post("/tasks/{task_id}/stop-recurrence", response_model=TaskResponse)
async def stop_recurrence(
    task_id: uuid.UUID, employer: Employer, service: TaskServiceDep
) -> TaskResponse:
    """Больше не выдавать это задание повторно."""
    return TaskResponse.model_validate(await service.stop_recurrence(employer, task_id))
