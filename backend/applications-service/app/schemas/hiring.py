"""Схемы процесса найма: этапы, ответственные, интервью, офферы, история.

Работодатель видит всё, включая оценки интервью и внутренние заметки.
Кандидат — этап, назначенные интервью, офферы и публичную часть истории.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

from app.models import HiringSource, HiringStage, HiringStatus

Text200 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Message = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]

InterviewKind = Literal["hr", "technical", "final", "other"]
InterviewFormat = Literal["online", "office", "phone"]
# Этапы, на которые работодатель переводит вручную. «Нанят» — только
# через принятый оффер.
ManualStage = Literal["new", "screening", "interview", "assessment", "offer"]


def _future(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Укажите дату и время с часовым поясом")
    if value <= datetime.now(UTC):
        raise ValueError("Дата должна быть в будущем")
    return value


# --- Команда (ответственные и интервьюеры) -------------------------------------------


class TeamMemberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Text200
    position: Text200 | None = None
    email: EmailStr | None = None


class TeamMemberUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Text200 | None = None
    position: Text200 | None = None
    email: EmailStr | None = None
    is_active: bool | None = None


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    position: str | None
    email: str | None
    is_active: bool
    created_at: datetime


class PersonBrief(BaseModel):
    """Сотрудник компании в карточках процесса."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    position: str | None


# --- Запросы работодателя -------------------------------------------------------------


class StageChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: ManualStage
    comment: Message | None = None


class ResponsibleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None — снять ответственного.
    responsible_id: uuid.UUID | None


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Причина — для истории, кандидат её не видит.
    reason: Message | None = None
    # Сообщение кандидату (уйдёт в уведомление и переписку).
    message: Message | None = None


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]


class InterviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: InterviewKind = "technical"
    title: Text200 | None = None
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    format: InterviewFormat = "online"
    location: Annotated[str, StringConstraints(max_length=500)] | None = None
    interviewer_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    note_for_candidate: Message | None = None

    _check_date = field_validator("scheduled_at")(_future)


class InterviewUpdate(BaseModel):
    """Перенос или изменение интервью; передаются только изменённые поля."""

    model_config = ConfigDict(extra="forbid")

    kind: InterviewKind | None = None
    title: Text200 | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)
    format: InterviewFormat | None = None
    location: Annotated[str, StringConstraints(max_length=500)] | None = None
    interviewer_ids: list[uuid.UUID] | None = Field(default=None, max_length=10)
    note_for_candidate: Message | None = None

    @field_validator("scheduled_at")
    @classmethod
    def _check_date(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _future(value)


class InterviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "no_show"]
    rating: int | None = Field(default=None, ge=1, le=5)
    feedback: Annotated[str, StringConstraints(max_length=4000)] | None = None


class InterviewCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Message | None = None


class OfferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # По умолчанию — название вакансии процесса.
    position_title: Text200 | None = None
    salary: int = Field(gt=0, le=100_000_000)
    currency: str = Field(default="RUB", pattern=r"^[A-Z]{3}$")
    salary_type: Literal["gross", "net"] = "gross"
    start_date: date | None = None
    employment_type: (
        Literal["full_time", "part_time", "project", "internship"] | None
    ) = None
    work_format: Literal["office", "remote", "hybrid"] | None = None
    benefits: Annotated[str, StringConstraints(max_length=4000)] | None = None
    message: Message | None = None
    # Сколько дней кандидат может ответить.
    expires_in_days: int = Field(default=7, ge=1, le=30)

    @field_validator("start_date")
    @classmethod
    def _check_start(cls, value: date | None) -> date | None:
        if value is not None and value < datetime.now(UTC).date():
            raise ValueError("Дата выхода не может быть в прошлом")
        return value


class CandidateReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Message | None = None


# --- Ответы ---------------------------------------------------------------------------


class InterviewResponse(BaseModel):
    """Интервью для работодателя (с оценкой и отзывом)."""

    id: uuid.UUID
    kind: InterviewKind
    title: str | None
    scheduled_at: datetime
    duration_minutes: int
    format: InterviewFormat
    location: str | None
    interviewers: list[PersonBrief]
    note_for_candidate: str | None
    status: str
    rating: int | None
    feedback: str | None
    completed_at: datetime | None
    created_at: datetime


class CandidateInterviewResponse(BaseModel):
    """Интервью для кандидата: без оценки и отзыва."""

    id: uuid.UUID
    kind: InterviewKind
    title: str | None
    scheduled_at: datetime
    duration_minutes: int
    format: InterviewFormat
    location: str | None
    interviewers: list[PersonBrief]
    note_for_candidate: str | None
    status: str


class OfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position_title: str
    salary: int
    currency: str
    salary_type: str
    start_date: date | None
    employment_type: str | None
    work_format: str | None
    benefits: str | None
    message: str | None
    expires_at: datetime
    status: str
    candidate_message: str | None
    responded_at: datetime | None
    created_at: datetime


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    # employer, candidate, system
    actor_role: str
    data: dict[str, Any]
    comment: str | None
    created_at: datetime


class EmployerEventResponse(EventResponse):
    actor_id: uuid.UUID | None
    visible_to_candidate: bool


class ProcessSummary(BaseModel):
    """Строка воронки работодателя."""

    id: uuid.UUID
    candidate_id: uuid.UUID
    source: HiringSource
    source_id: uuid.UUID
    vacancy_id: str | None
    vacancy_title: str
    company_name: str
    company_id: uuid.UUID | None
    stage: HiringStage
    status: HiringStatus
    responsible: PersonBrief | None
    # Ближайшее назначенное интервью.
    next_interview_at: datetime | None
    # Статус последнего оффера.
    offer_status: str | None
    stage_changed_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProcessDetail(ProcessSummary):
    rejection_reason: str | None
    interviews: list[InterviewResponse]
    offers: list[OfferResponse]
    history: list[EmployerEventResponse]


class CandidateProcess(BaseModel):
    """Процесс найма глазами кандидата."""

    id: uuid.UUID
    employer_id: uuid.UUID
    source: HiringSource
    source_id: uuid.UUID
    vacancy_id: str | None
    vacancy_title: str
    company_name: str
    company_id: uuid.UUID | None
    stage: HiringStage
    status: HiringStatus
    # Контактное лицо со стороны компании.
    responsible: PersonBrief | None
    interviews: list[CandidateInterviewResponse]
    offers: list[OfferResponse]
    history: list[EventResponse]
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class Option(BaseModel):
    id: str
    title: str


class HiringDictionaries(BaseModel):
    """Подписи для интерфейса."""

    stages: list[Option]
    statuses: list[Option]
    interview_kinds: list[Option]
    interview_formats: list[Option]
    interview_statuses: list[Option]
    offer_statuses: list[Option]
    event_types: list[Option]
