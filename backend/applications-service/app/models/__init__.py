"""ORM-модели applications-service.

Приглашения работодателей, отклики кандидатов и процесс найма, который
начинается с отклика или принятого приглашения: этапы, интервью, офферы,
ответственные и история.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from benefit_common.outbox import OutboxMessageMixin
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    # Компания работодателя в employer-service: по ней фронтенд показывает
    # актуальный статус проверки («Проверенный работодатель»).
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
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
    # Компания работодателя в employer-service: по ней фронтенд показывает
    # актуальный статус проверки («Проверенный работодатель»).
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_to: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    cover_letter: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=ApplicationStatus.NEW)
    # Комментарий работодателя к последней смене статуса.
    employer_message: Mapped[str | None] = mapped_column(Text)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --- Процесс найма --------------------------------------------------------------


class HiringStage(StrEnum):
    """Этапы воронки по порядку."""

    NEW = "new"
    SCREENING = "screening"
    INTERVIEW = "interview"
    ASSESSMENT = "assessment"
    OFFER = "offer"
    HIRED = "hired"


STAGE_ORDER = list(HiringStage)


class HiringStatus(StrEnum):
    ACTIVE = "active"
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class HiringSource(StrEnum):
    APPLICATION = "application"
    INVITATION = "invitation"


class TeamMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Сотрудник компании, участвующий в найме: рекрутер, нанимающий
    менеджер, интервьюер. Назначается ответственным и интервьюером."""

    __tablename__ = "team_members"

    employer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    position: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class HiringProcess(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Процесс найма кандидата на вакансию работодателя."""

    __tablename__ = "hiring_processes"
    __table_args__ = (UniqueConstraint("source", "source_id"),)

    employer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(index=True)
    # С чего начался процесс: отклик или принятое приглашение.
    source: Mapped[str] = mapped_column(String(16))
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    vacancy_id: Mapped[str | None] = mapped_column(String(64), index=True)
    vacancy_title: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200))
    # Компания работодателя в employer-service: по ней фронтенд показывает
    # актуальный статус проверки («Проверенный работодатель»).
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    stage: Mapped[str] = mapped_column(String(16), default=HiringStage.NEW)
    status: Mapped[str] = mapped_column(String(16), default=HiringStatus.ACTIVE)
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("team_members.id", ondelete="SET NULL")
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    stage_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    responsible: Mapped[TeamMember | None] = relationship(lazy="selectin")
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="process",
        lazy="selectin",
        order_by="Interview.scheduled_at",
        cascade="all, delete-orphan",
    )
    offers: Mapped[list["JobOffer"]] = relationship(
        back_populates="process",
        lazy="selectin",
        order_by="JobOffer.created_at",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["HiringEvent"]] = relationship(
        back_populates="process",
        lazy="selectin",
        order_by="HiringEvent.created_at",
        cascade="all, delete-orphan",
    )


class InterviewStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Interview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "interviews"

    process_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hiring_processes.id", ondelete="CASCADE"), index=True
    )
    # hr, technical, final, other
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str | None] = mapped_column(String(200))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(SmallInteger)
    # online, office, phone
    format: Mapped[str] = mapped_column(String(16))
    # Ссылка на видеовстречу, адрес или телефон.
    location: Mapped[str | None] = mapped_column(String(500))
    interviewer_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), default=list)
    # Сообщение кандидату (как подготовиться и т. п.).
    note_for_candidate: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=InterviewStatus.SCHEDULED)
    # Итоги видит только работодатель.
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    feedback: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    process: Mapped[HiringProcess] = relationship(back_populates="interviews")


class OfferStatus(StrEnum):
    SENT = "sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class JobOffer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Оффер кандидату. Активным может быть только один оффер процесса."""

    __tablename__ = "job_offers"

    process_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hiring_processes.id", ondelete="CASCADE"), index=True
    )
    position_title: Mapped[str] = mapped_column(String(200))
    salary: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    # gross (до вычета НДФЛ) или net (на руки).
    salary_type: Mapped[str] = mapped_column(String(8), default="gross")
    start_date: Mapped[date | None] = mapped_column(Date)
    employment_type: Mapped[str | None] = mapped_column(String(16))
    work_format: Mapped[str | None] = mapped_column(String(16))
    benefits: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default=OfferStatus.SENT)
    candidate_message: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    process: Mapped[HiringProcess] = relationship(back_populates="offers")


class HiringEvent(UUIDPrimaryKeyMixin, Base):
    """Запись истории процесса: кто, когда и что изменил."""

    __tablename__ = "hiring_events"

    process_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hiring_processes.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(32))
    # Автор: работодатель, кандидат или система (None).
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_role: Mapped[str] = mapped_column(String(16))
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    comment: Mapped[str | None] = mapped_column(Text)
    # Внутренние события (заметки, оценки, ответственный) кандидат не видит.
    visible_to_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    process: Mapped[HiringProcess] = relationship(back_populates="events")


class OutboxMessage(OutboxMessageMixin, Base):
    """Уведомления участникам (через notification-service)."""

    __tablename__ = "outbox_messages"


__all__ = [
    "STAGE_ORDER",
    "Application",
    "ApplicationStatus",
    "Base",
    "HiringEvent",
    "HiringProcess",
    "HiringSource",
    "HiringStage",
    "HiringStatus",
    "Interview",
    "InterviewStatus",
    "Invitation",
    "InvitationStatus",
    "JobOffer",
    "OfferStatus",
    "OutboxMessage",
    "TeamMember",
]
