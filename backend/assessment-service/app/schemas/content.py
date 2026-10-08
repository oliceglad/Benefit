"""Схемы управления контентом тестов (только для администраторов).

Пакет тестов (``TestPack``) — формат импорта/экспорта. Пакеты содержат
правильные ответы, поэтому хранятся вне репозитория.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from benefit_common.dictionaries import Grade, ITRole
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import TaskKind

Key = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TaskOptionIn(BaseModel):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9]{1,8}$")]
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]


class TaskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Key = Field(description="Стабильный ключ задачи внутри теста")
    kind: TaskKind
    prompt: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]
    code: str | None = Field(default=None, max_length=8000)
    options: list[TaskOptionIn] = Field(default_factory=list, max_length=10)
    correct: list[Text] = Field(min_length=1, max_length=20)
    points: int = Field(ge=1, le=100)
    time_limit_seconds: int = Field(ge=10, le=3600)
    skills: list[Text] = Field(default_factory=list, max_length=20)
    explanation: str | None = Field(default=None, max_length=4000)
    is_active: bool = True

    @model_validator(mode="after")
    def _check_answers(self) -> Self:
        ids = [o.id for o in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.key}: id вариантов должны быть уникальны")
        if self.kind == TaskKind.TEXT:
            if self.options:
                raise ValueError(f"{self.key}: у текстовой задачи нет вариантов")
            return self
        if len(self.options) < 2:
            raise ValueError(f"{self.key}: нужно минимум два варианта ответа")
        if not set(self.correct) <= set(ids):
            raise ValueError(f"{self.key}: правильный ответ не из списка вариантов")
        if self.kind == TaskKind.SINGLE_CHOICE and len(self.correct) != 1:
            raise ValueError(f"{self.key}: у одиночного выбора один правильный ответ")
        return self


class TestIn(BaseModel):
    """Тест целиком: метаданные и банк задач."""

    __test__ = False  # не тестовый класс для pytest
    model_config = ConfigDict(extra="forbid")

    slug: Key
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    description: str = Field(default="", max_length=4000)
    specialization: ITRole
    grade: Grade
    time_limit_seconds: int = Field(ge=60, le=4 * 3600)
    tasks_per_attempt: int = Field(ge=1, le=100)
    is_active: bool = True
    tasks: list[TaskIn] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _check_tasks(self) -> Self:
        keys = [t.key for t in self.tasks]
        if len(keys) != len(set(keys)):
            raise ValueError("Ключи задач в тесте должны быть уникальны")
        active = sum(1 for t in self.tasks if t.is_active)
        if self.tasks_per_attempt > active:
            raise ValueError(
                f"В попытке {self.tasks_per_attempt} задач, а активных в банке {active}"
            )
        return self


class TestPack(BaseModel):
    __test__ = False
    format_version: Literal[1] = 1
    tests: list[TestIn] = Field(min_length=1)


class AdminTestSummary(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    specialization: ITRole
    grade: Grade
    is_active: bool
    tasks_total: int
    tasks_active: int
    attempts: int
    updated_at: datetime
    updated_by: uuid.UUID | None


class AdminTestDetail(TestIn):
    __test__ = False
    id: uuid.UUID
    updated_at: datetime
    updated_by: uuid.UUID | None


class ActiveUpdate(BaseModel):
    is_active: bool


class ImportReport(BaseModel):
    created: list[str]
    updated: list[str]
    skipped: list[str]
