"""ORM-модели assessment-service.

* ``Assessment`` — тест для пары «специализация + грейд» с банком задач;
* ``AssessmentTask`` — задача теста (баллы, лимит времени, навыки);
* ``Attempt`` — попытка кандидата: опрос, время, результат;
* ``AttemptTask`` — задача в попытке: ответ, баллы, затраченное время.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from benefit_common.outbox import OutboxMessageMixin
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TaskKind(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TEXT = "text"


class AttemptStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    # Время теста вышло до завершения: неотвеченные задачи — 0 баллов.
    EXPIRED = "expired"


class AssignmentStatus(StrEnum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    # Срок прошёл, а кандидат так и не начал тест.
    EXPIRED = "expired"


class Outcome(StrEnum):
    NOT_CONFIRMED = "not_confirmed"
    CONFIRMED = "confirmed"
    EXCEEDED = "exceeded"


class Assessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessments"

    slug: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(32), index=True)
    grade: Mapped[str] = mapped_column(String(16))
    time_limit_seconds: Mapped[int]
    # Сколько задач из банка попадает в одну попытку.
    tasks_per_attempt: Mapped[int]
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    # Администратор, последним изменивший тест (None — импорт из CLI).
    updated_by: Mapped[uuid.UUID | None]
    # Владелец-работодатель. None — тест платформы: только такие
    # подтверждают грейд и видны в общем каталоге.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(index=True)

    tasks: Mapped[list["AssessmentTask"]] = relationship(
        back_populates="assessment", order_by="AssessmentTask.position"
    )


class AssessmentTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_tasks"
    __table_args__ = (UniqueConstraint("assessment_id", "key"),)

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True
    )
    # Стабильный ключ задачи в seed-данных.
    key: Mapped[str] = mapped_column(String(64))
    position: Mapped[int]
    kind: Mapped[str] = mapped_column(String(32))
    prompt: Mapped[str] = mapped_column(Text)
    code: Mapped[str | None] = mapped_column(Text)
    options: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    # Правильные варианты (id) или допустимые текстовые ответы.
    correct: Mapped[list[str]] = mapped_column(JSONB)
    points: Mapped[int]
    time_limit_seconds: Mapped[int]
    skills: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    explanation: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    assessment: Mapped[Assessment] = relationship(back_populates="tasks")


class Attempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attempts"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id"), index=True
    )
    specialization: Mapped[str] = mapped_column(String(32))
    target_grade: Mapped[str] = mapped_column(String(16))
    # Грейд, указанный в резюме на момент начала попытки.
    claimed_grade: Mapped[str | None] = mapped_column(String(16))
    # Ответы на опрос перед тестом (отрасль, специализация, опыт, навыки).
    survey: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default=AttemptStatus.IN_PROGRESS)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None]
    score: Mapped[float | None]
    max_score: Mapped[int]
    percent: Mapped[float | None]
    outcome: Mapped[str | None] = mapped_column(String(16))
    # Подтверждённый попыткой грейд (None — не подтверждён).
    confirmed_grade: Mapped[str | None] = mapped_column(String(16))
    # Попытка по тесту, который прислал работодатель (грейд не меняет).
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_assignments.id", ondelete="SET NULL"), index=True
    )

    assessment: Mapped[Assessment] = relationship()
    tasks: Mapped[list["AttemptTask"]] = relationship(
        back_populates="attempt", order_by="AttemptTask.position"
    )


class AttemptTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attempt_tasks"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attempts.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_tasks.id"))
    position: Mapped[int]
    max_points: Mapped[int]
    time_limit_seconds: Mapped[int]
    # Выдача задачи кандидату — с этого момента идёт её время.
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_spent_seconds: Mapped[float | None]
    answer: Mapped[Any | None] = mapped_column(JSONB)
    is_correct: Mapped[bool | None]
    points_awarded: Mapped[float] = mapped_column(default=0, server_default="0")
    timed_out: Mapped[bool] = mapped_column(default=False, server_default="false")
    skipped: Mapped[bool] = mapped_column(default=False, server_default="false")

    attempt: Mapped[Attempt] = relationship(back_populates="tasks")
    task: Mapped[AssessmentTask] = relationship()


class TestAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Тест работодателя, отправленный кандидату в переписке."""

    __test__ = False  # не тестовый класс для pytest
    __tablename__ = "test_assignments"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id"), index=True
    )
    employer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(index=True)
    conversation_id: Mapped[uuid.UUID]
    # Снимок из переписки: от кого и по какой вакансии тест.
    company_name: Mapped[str] = mapped_column(String(200))
    vacancy_title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str | None] = mapped_column(Text)
    # Начать тест нужно до этого момента.
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default=AssignmentStatus.ASSIGNED)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assessment: Mapped[Assessment] = relationship()


class OutboxMessage(OutboxMessageMixin, Base):
    """Сообщения в candidate-service и notification-service."""

    __tablename__ = "outbox_messages"


__all__ = [
    "AssignmentStatus",
    "TestAssignment",
    "Assessment",
    "AssessmentTask",
    "Attempt",
    "AttemptStatus",
    "AttemptTask",
    "Base",
    "Outcome",
    "OutboxMessage",
    "TaskKind",
]
