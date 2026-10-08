"""ORM-модели chat-service.

* ``Conversation`` — диалог кандидата и работодателя по приглашению;
* ``Message`` — сообщение (текст, системное, задание, решение задания);
* ``Attachment`` — файл, загруженный в диалог и прикреплённый к сообщению;
* ``Task`` — регулярное задание от работодателя кандидату.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from benefit_common.outbox import OutboxMessageMixin
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ConversationStatus(StrEnum):
    OPEN = "open"
    # Приглашение отклонено или отозвано: переписка только для чтения.
    CLOSED = "closed"


class MessageKind(StrEnum):
    TEXT = "text"
    SYSTEM = "system"
    TASK = "task"
    TASK_SUBMISSION = "task_submission"
    # Тест от работодателя (карточка с кнопкой «Начать»), из assessment-service.
    ASSESSMENT = "assessment"


class TaskStatus(StrEnum):
    ASSIGNED = "assigned"
    SUBMITTED = "submitted"
    PASSED = "passed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ResponseType(StrEnum):
    # Кандидат решил задачу.
    SOLUTION = "solution"
    # Кандидат предложил подход к решению.
    APPROACH = "approach"


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    # Источник переписки: приглашение работодателя или отклик кандидата.
    source: Mapped[str] = mapped_column(String(16), default="invitation")
    # id приглашения или отклика (в зависимости от source).
    invitation_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(index=True)
    employer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    vacancy_title: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200))
    invitation_status: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default=ConversationStatus.OPEN)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidate_last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    employer_last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    def is_participant(self, user_id: uuid.UUID) -> bool:
        return user_id in (self.candidate_id, self.employer_id)

    def other_party(self, user_id: uuid.UUID) -> uuid.UUID:
        return self.employer_id if user_id == self.candidate_id else self.candidate_id


class Message(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        # Идемпотентность отправки: повтор с тем же client_id не дублирует.
        UniqueConstraint("conversation_id", "client_id"),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    # None — системное сообщение.
    sender_id: Mapped[uuid.UUID | None]
    kind: Mapped[str] = mapped_column(String(16), default=MessageKind.TEXT)
    text: Mapped[str] = mapped_column(Text, default="")
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL")
    )
    client_id: Mapped[str | None] = mapped_column(String(64))
    # Данные для отображения карточки (например, assignment_id теста).
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    # Монотонный номер для стабильной сортировки при равном времени.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="message", order_by="Attachment.created_at"
    )


class Attachment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attachments"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    uploader_id: Mapped[uuid.UUID]
    # None — загружен, но ещё не отправлен в сообщении.
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int]
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)

    message: Mapped[Message | None] = relationship(back_populates="attachments")


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Регулярное задание: работодатель выдаёт, кандидат решает или
    предлагает подход, работодатель оценивает."""

    __tablename__ = "tasks"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    employer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default=TaskStatus.ASSIGNED)

    response_type: Mapped[str | None] = mapped_column(String(16))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submission_message_id: Mapped[uuid.UUID | None]
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[int | None]
    feedback: Mapped[str | None] = mapped_column(Text)
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Повтор: через сколько дней выдать следующее задание серии.
    recurrence_days: Mapped[int | None]
    next_issue_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Первое задание серии (у первого — None).
    series_id: Mapped[uuid.UUID | None]


class OutboxMessage(OutboxMessageMixin, Base):
    """Уведомления (notification-service) и активность (candidate-service)."""

    __tablename__ = "outbox_messages"


__all__ = [
    "Attachment",
    "Base",
    "Conversation",
    "ConversationStatus",
    "Message",
    "MessageKind",
    "OutboxMessage",
    "ResponseType",
    "Task",
    "TaskStatus",
]
