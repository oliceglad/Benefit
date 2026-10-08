"""Схемы API тестирования."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from benefit_common.dictionaries import Grade, Industry, ITRole
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import AttemptStatus, Outcome, TaskKind

SkillName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]


class SurveyAnswers(BaseModel):
    """Опрос перед тестом: отрасль, специализация, предполагаемый грейд."""

    model_config = ConfigDict(extra="forbid")

    industry: Industry
    specialization: ITRole
    target_grade: Grade = Field(description="Грейд, который кандидат подтверждает")
    years_of_experience: float = Field(ge=0, le=50)
    skills: list[SkillName] = Field(
        default_factory=list,
        max_length=50,
        description="Основной стек: задачи подбираются в первую очередь по нему",
    )


class Option(BaseModel):
    id: str
    title: str


class SpecializationOption(Option):
    # Грейды, для которых есть тест по специализации.
    grades: list[Grade]


class SurveyPrefill(BaseModel):
    industry: Industry | None
    specialization: ITRole | None
    claimed_grade: Grade | None
    years_of_experience: float | None
    skills: list[str]


class CooldownInfo(BaseModel):
    specialization: ITRole
    available_at: datetime


class SurveyOptions(BaseModel):
    industries: list[Option]
    specializations: list[SpecializationOption]
    grades: list[Option]
    prefill: SurveyPrefill | None
    cooldowns: list[CooldownInfo]
    pass_percent: float
    exceed_percent: float


class AssessmentInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    description: str
    specialization: ITRole
    grade: Grade
    time_limit_seconds: int
    tasks_per_attempt: int


class TaskOption(BaseModel):
    id: str
    text: str


class TaskView(BaseModel):
    """Текущая задача. Правильный ответ не передаётся."""

    attempt_task_id: uuid.UUID
    position: int
    total: int
    kind: TaskKind
    prompt: str
    code: str | None
    options: list[TaskOption]
    points: int
    skills: list[str]
    time_limit_seconds: int
    # Осталось на задачу с учётом общего лимита теста.
    time_left_seconds: float
    started_at: datetime


class AnswerRequest(BaseModel):
    attempt_task_id: uuid.UUID
    # Список id вариантов, текст или null (пропустить задачу).
    answer: list[str] | str | None = None


class TaskResult(BaseModel):
    position: int
    prompt: str
    kind: TaskKind
    skills: list[str]
    max_points: int
    points_awarded: float
    is_correct: bool | None
    time_limit_seconds: int
    time_spent_seconds: float | None
    timed_out: bool
    skipped: bool


class SkillScore(BaseModel):
    skill: str
    points: float
    max_points: int
    percent: float


class AttemptResult(BaseModel):
    score: float
    max_score: int
    percent: float
    # None — тест работодателя (грейд не подтверждает).
    outcome: Outcome | None
    target_grade: Grade
    # Подтверждённый грейд (None — не подтверждён). Ниже целевого не бывает.
    confirmed_grade: Grade | None
    message: str
    duration_seconds: float
    tasks: list[TaskResult]
    skills: list[SkillScore]


class AttemptResponse(BaseModel):
    id: uuid.UUID
    assessment: AssessmentInfo
    status: AttemptStatus
    survey: dict[str, Any]
    claimed_grade: Grade | None
    started_at: datetime
    deadline_at: datetime
    finished_at: datetime | None
    time_left_seconds: float
    total_tasks: int
    answered_tasks: int
    max_score: int
    result: AttemptResult | None


class AnswerResponse(BaseModel):
    time_spent_seconds: float
    timed_out: bool
    finished: bool
    attempt: AttemptResponse


class AttemptSummary(BaseModel):
    id: uuid.UUID
    title: str
    specialization: ITRole
    target_grade: Grade
    industry: Industry | None
    status: AttemptStatus
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    percent: float | None
    outcome: Outcome | None
    confirmed_grade: Grade | None
    # Тест прислал работодатель.
    assignment_id: uuid.UUID | None = None


class VerifiedCategory(BaseModel):
    specialization: ITRole
    grade: Grade
    verified_at: datetime
    valid_until: datetime
    attempt_id: uuid.UUID
    percent: float


class AssessmentStatus(BaseModel):
    """Текущий статус кандидата: подтверждённая категория, ограничения."""

    verified: VerifiedCategory | None
    active_attempt_id: uuid.UUID | None
    cooldowns: list[CooldownInfo]
    attempts_total: int
