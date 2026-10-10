"""Прохождение тестирования кандидатом.

Тест на грейд: ``GET /survey`` (опрос и предзаполнение из профиля) →
``POST /attempts`` (ответы опроса, старт). Тест на навык (английский, SQL,
Git…): ``GET /skill-tests`` → ``POST /skill-tests/{id}/attempts``. Дальше
одинаково: цикл ``GET /attempts/{id}/current-task`` и
``POST /attempts/{id}/answers`` → результат в ``GET /attempts/{id}``.

Время задачи идёт с момента её выдачи (``current-task``) и считается на
сервере; ответ после лимита задачи не засчитывается.
"""

import uuid

from benefit_common.security import Candidate, CurrentPrincipal
from fastapi import APIRouter, status

from app.api.deps import AttemptServiceDep
from app.models import AssessmentKind
from app.schemas.assessment import (
    AnswerRequest,
    AnswerResponse,
    AssessmentInfo,
    AssessmentStatus,
    AttemptResponse,
    AttemptSummary,
    SkillTestOption,
    SurveyAnswers,
    SurveyOptions,
    TaskView,
)

router = APIRouter(tags=["assessments"])


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/tests", response_model=list[AssessmentInfo])
async def list_tests(
    _: CurrentPrincipal,
    service: AttemptServiceDep,
    kind: AssessmentKind | None = None,
) -> list:
    """Каталог тестов (без задач): на грейд и на навыки."""
    return [AssessmentInfo.model_validate(a) for a in await service.catalog(kind)]


@router.get("/survey", response_model=SurveyOptions)
async def survey(principal: Candidate, service: AttemptServiceDep) -> SurveyOptions:
    """Варианты опроса и предзаполнение из профиля кандидата."""
    return await service.survey(principal)


@router.get("/status", response_model=AssessmentStatus)
async def assessment_status(
    principal: Candidate, service: AttemptServiceDep
) -> AssessmentStatus:
    """Текущая подтверждённая категория, активная попытка, ограничения."""
    return await service.status(principal.id)


@router.post(
    "/attempts", response_model=AttemptResponse, status_code=status.HTTP_201_CREATED
)
async def start_attempt(
    survey: SurveyAnswers, principal: Candidate, service: AttemptServiceDep
) -> AttemptResponse:
    """Начать тест по ответам опроса (специализация + предполагаемый грейд)."""
    return await service.start(principal, survey)


@router.get("/skill-tests", response_model=list[SkillTestOption])
async def skill_tests(principal: Candidate, service: AttemptServiceDep) -> list:
    """Тесты на навыки: шкала уровней, подтверждённый уровень, когда можно
    пройти повторно."""
    return await service.skill_tests(principal)


@router.post(
    "/skill-tests/{assessment_id}/attempts",
    response_model=AttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_skill_attempt(
    assessment_id: uuid.UUID, principal: Candidate, service: AttemptServiceDep
) -> AttemptResponse:
    """Начать тест на навык. Уровень определяется по набранному проценту:
    самая высокая ступень шкалы, порог которой достигнут."""
    return await service.start_skill(principal, assessment_id)


@router.get("/attempts", response_model=list[AttemptSummary])
async def history(principal: Candidate, service: AttemptServiceDep) -> list:
    """История опросов и тестов."""
    return await service.history(principal)


@router.get("/attempts/{attempt_id}", response_model=AttemptResponse)
async def get_attempt(
    attempt_id: uuid.UUID, principal: Candidate, service: AttemptServiceDep
) -> AttemptResponse:
    return await service.get(principal, attempt_id)


@router.get("/attempts/{attempt_id}/current-task", response_model=TaskView)
async def current_task(
    attempt_id: uuid.UUID, principal: Candidate, service: AttemptServiceDep
) -> TaskView:
    """Текущая задача. Первый запрос запускает её таймер."""
    return await service.current_task(principal, attempt_id)


@router.post("/attempts/{attempt_id}/answers", response_model=AnswerResponse)
async def answer(
    attempt_id: uuid.UUID,
    data: AnswerRequest,
    principal: Candidate,
    service: AttemptServiceDep,
) -> AnswerResponse:
    """Ответ на текущую задачу (``answer: null`` — пропустить)."""
    return await service.answer(principal, attempt_id, data)


@router.post("/attempts/{attempt_id}/finish", response_model=AttemptResponse)
async def finish(
    attempt_id: uuid.UUID, principal: Candidate, service: AttemptServiceDep
) -> AttemptResponse:
    """Досрочно завершить тест: оставшиеся задачи получают 0 баллов."""
    return await service.finish(principal, attempt_id)
