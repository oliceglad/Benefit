"""Схемы тестов работодателей и их отправки кандидатам."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Self

from benefit_common.dictionaries import Grade, ITRole
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import AssignmentStatus, TaskKind
from app.schemas.content import TaskIn


class EmployerTestIn(BaseModel):
    """Тест работодателя. По умолчанию в попытку входят все задачи."""

    model_config = ConfigDict(extra="forbid")

    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    description: str = Field(default="", max_length=4000)
    specialization: ITRole
    grade: Grade
    time_limit_seconds: int = Field(ge=60, le=4 * 3600)
    tasks_per_attempt: int | None = Field(default=None, ge=1, le=100)
    tasks: list[TaskIn] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _check_tasks(self) -> Self:
        keys = [t.key for t in self.tasks]
        if len(keys) != len(set(keys)):
            raise ValueError("Ключи задач в тесте должны быть уникальны")
        active = sum(1 for t in self.tasks if t.is_active)
        if self.tasks_per_attempt is None:
            self.tasks_per_attempt = active
        if not 1 <= self.tasks_per_attempt <= active:
            raise ValueError(
                f"В попытке {self.tasks_per_attempt} задач, а активных в тесте {active}"
            )
        return self


class EmployerTestSummary(BaseModel):
    id: uuid.UUID
    title: str
    specialization: ITRole
    grade: Grade
    is_active: bool
    tasks_total: int
    tasks_per_attempt: int
    time_limit_seconds: int
    assignments: int
    updated_at: datetime


class EmployerTestDetail(EmployerTestIn):
    id: uuid.UUID
    is_active: bool
    updated_at: datetime


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID
    # Начать тест нужно до этого срока.
    due_at: datetime
    message: str | None = Field(default=None, max_length=2000)


class AssignmentTest(BaseModel):
    title: str
    description: str
    specialization: ITRole
    grade: Grade
    time_limit_seconds: int
    tasks_per_attempt: int


class AssignmentResult(BaseModel):
    attempt_id: uuid.UUID
    status: str
    score: float | None
    max_score: int
    percent: float | None
    duration_seconds: float | None


class AssignmentResponse(BaseModel):
    """Тест, отправленный кандидату (вид кандидата)."""

    id: uuid.UUID
    status: AssignmentStatus
    test: AssignmentTest
    employer_id: uuid.UUID
    candidate_id: uuid.UUID
    conversation_id: uuid.UUID
    company_name: str
    vacancy_title: str
    message: str | None
    due_at: datetime
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    result: AssignmentResult | None


class AnswerReview(BaseModel):
    """Задача с ответом кандидата — для работодателя (автора теста)."""

    position: int
    kind: TaskKind
    prompt: str
    code: str | None
    options: list[dict[str, str]]
    correct: list[str]
    answer: Any
    is_correct: bool | None
    points_awarded: float
    max_points: int
    time_spent_seconds: float | None
    time_limit_seconds: int
    timed_out: bool
    skipped: bool


class EmployerAssignmentResponse(AssignmentResponse):
    answers: list[AnswerReview]
