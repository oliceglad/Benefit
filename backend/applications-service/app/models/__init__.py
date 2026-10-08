"""ORM-модели applications-service.

Сейчас — приглашения работодателей кандидатам. Отклики кандидатов на
вакансии появятся здесь же, когда будет сервис вакансий.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from benefit_common.outbox import OutboxMessageMixin
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class Invitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invitations"

    employer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Вакансия. vacancy_id — ссылка на будущий сервис вакансий.
    vacancy_id: Mapped[str | None] = mapped_column(String(64))
    vacancy_title: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200))
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_to: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    work_format: Mapped[str | None] = mapped_column(String(16))
    city: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(16), default=InvitationStatus.PENDING)
    response_message: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApplicationStatus(StrEnum):
    NEW = "new"
    VIEWED = "viewed"
    # Работодатель приглашает кандидата на собеседование.
    INVITED = "invited"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Application(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Отклик кандидата на опубликованную вакансию."""

    __tablename__ = "applications"

    vacancy_id: Mapped[uuid.UUID] = mapped_column(index=True)
    employer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(index=True)
    # Снимок вакансии на момент отклика.
    vacancy_title: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200))
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_to: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    cover_letter: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=ApplicationStatus.NEW)
    # Комментарий работодателя к последней смене статуса.
    employer_message: Mapped[str | None] = mapped_column(Text)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxMessage(OutboxMessageMixin, Base):
    """Уведомления участникам (через notification-service)."""

    __tablename__ = "outbox_messages"


__all__ = [
    "Application",
    "ApplicationStatus",
    "Base",
    "Invitation",
    "InvitationStatus",
    "OutboxMessage",
]
