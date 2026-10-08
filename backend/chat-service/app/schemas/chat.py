"""Схемы API чата и заданий."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.config import settings
from app.models import ConversationStatus, MessageKind, ResponseType, TaskStatus

ClientId = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size: int
    created_at: datetime


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID | None
    kind: MessageKind
    text: str
    task_id: uuid.UUID | None
    client_id: str | None
    data: dict[str, Any]
    attachments: list[AttachmentResponse]
    created_at: datetime


class MessageCreate(BaseModel):
    """Новое сообщение. Файлы сначала загружаются в диалог, затем
    перечисляются в ``attachment_ids``."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(default="", max_length=settings.message_max_length)
    attachment_ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=settings.max_attachments_per_message
    )
    # Ключ идемпотентности от клиента: повторная отправка не дублирует.
    client_id: ClientId | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    source: str
    invitation_id: uuid.UUID
    candidate_id: uuid.UUID
    employer_id: uuid.UUID
    vacancy_title: str
    company_name: str
    invitation_status: str
    status: ConversationStatus
    last_message: MessageResponse | None
    last_message_at: datetime | None
    unread_count: int
    # Когда собеседник прочитал переписку (для галочек «прочитано»).
    other_party_last_read_at: datetime | None
    created_at: datetime


class ReadRequest(BaseModel):
    # Отметить прочитанным всё до этого сообщения включительно.
    message_id: uuid.UUID | None = None


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)
    ]
    due_at: datetime
    attachment_ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=settings.max_attachments_per_message
    )
    # Выдавать такое же задание повторно через N дней (регулярное задание).
    recurrence_days: int | None = Field(default=None, ge=1, le=90)


class TaskSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_type: ResponseType
    text: str = Field(default="", max_length=8000)
    attachment_ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=settings.max_attachments_per_message
    )


class TaskReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["passed", "failed"]
    score: int | None = Field(default=None, ge=0, le=100)
    feedback: str | None = Field(default=None, max_length=4000)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    employer_id: uuid.UUID
    candidate_id: uuid.UUID
    title: str
    description: str
    due_at: datetime
    status: TaskStatus
    response_type: ResponseType | None
    submitted_at: datetime | None
    submission_message_id: uuid.UUID | None
    reviewed_at: datetime | None
    score: int | None
    feedback: str | None
    recurrence_days: int | None
    next_issue_at: datetime | None
    series_id: uuid.UUID | None
    created_at: datetime


class InternalMessage(BaseModel):
    """Сообщение от другого сервиса (например, тест от работодателя)."""

    kind: Literal["system", "assessment"]
    # Отправитель для карточки теста — работодатель; у системных — None.
    sender_id: uuid.UUID | None = None
    text: Annotated[str, StringConstraints(min_length=1, max_length=8000)]
    data: dict[str, Any] = Field(default_factory=dict)
    client_id: ClientId


class ConversationInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invitation_id: uuid.UUID
    candidate_id: uuid.UUID
    employer_id: uuid.UUID
    vacancy_title: str
    company_name: str
    status: ConversationStatus


class ConversationSync(BaseModel):
    """От applications-service: создание диалога и смена статуса приглашения."""

    invitation_id: uuid.UUID
    candidate_id: uuid.UUID
    employer_id: uuid.UUID
    vacancy_title: str
    company_name: str
    source: Literal["invitation", "application"] = "invitation"
    # Статус приглашения или отклика.
    invitation_status: Literal[
        "pending",
        "accepted",
        "declined",
        "withdrawn",
        "expired",
        "new",
        "viewed",
        "invited",
        "rejected",
    ]
    # Текст события для системного сообщения в переписке.
    event_text: str | None = None
    # Ключ события: повторная доставка не дублирует системное сообщение.
    event_key: str
