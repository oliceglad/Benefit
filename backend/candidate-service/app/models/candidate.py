"""Профиль (резюме) кандидата и связанные данные.

Вложенные списки (опыт, образование, навыки…) хранятся в JSONB: профиль
читается и редактируется целиком, а поиск и подбор строят собственные
индексы по событиям и внутреннему API этого сервиса.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ProfileStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


def _json_list() -> Any:
    return mapped_column(JSONB, default=list, server_default="[]")


class CandidateProfile(TimestampMixin, Base):
    __tablename__ = "candidate_profiles"

    # Идентификатор пользователя из auth-service (claim ``sub``).
    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(
        String(16), default=ProfileStatus.DRAFT, server_default=ProfileStatus.DRAFT
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Личные данные
    last_name: Mapped[str | None] = mapped_column(String(100))
    first_name: Mapped[str | None] = mapped_column(String(100))
    middle_name: Mapped[str | None] = mapped_column(String(100))
    birth_date: Mapped[date | None] = mapped_column(Date)
    city: Mapped[str | None] = mapped_column(String(100))
    relocation_ready: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )

    # Контакты
    phone: Mapped[str | None] = mapped_column(String(32))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    telegram: Mapped[str | None] = mapped_column(String(64))
    links: Mapped[list[dict[str, Any]]] = _json_list()

    # Специализация
    headline: Mapped[str | None] = mapped_column(String(200))
    about: Mapped[str | None] = mapped_column(Text)
    grade: Mapped[str | None] = mapped_column(String(16))
    # Грейд, подтверждённый тестированием (заполняет assessment-service).
    verified_grade: Mapped[str | None] = mapped_column(String(16))
    grade_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    roles: Mapped[list[str]] = _json_list()
    skills: Mapped[list[dict[str, Any]]] = _json_list()
    soft_skills: Mapped[list[str]] = _json_list()
    languages: Mapped[list[dict[str, Any]]] = _json_list()

    # Резюме
    experience: Mapped[list[dict[str, Any]]] = _json_list()
    education: Mapped[list[dict[str, Any]]] = _json_list()
    courses: Mapped[list[dict[str, Any]]] = _json_list()
    projects: Mapped[list[dict[str, Any]]] = _json_list()

    # Пожелания к работе
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str] = mapped_column(
        String(3), default="RUB", server_default="RUB"
    )
    employment_types: Mapped[list[str]] = _json_list()
    work_formats: Mapped[list[str]] = _json_list()
    job_search_status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active"
    )

    # Что видно работодателю (см. schemas.profile.PrivacySettings).
    privacy: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    # Связь с участником ФСП.
    fsp_participant_id: Mapped[str | None] = mapped_column(String(64))
    fsp_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CandidatePhoto(TimestampMixin, Base):
    __tablename__ = "candidate_photos"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"), primary_key=True
    )
    content: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(String(32))


class FspAchievement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Достижение в соревнованиях ФСП. Источник — только API ФСП."""

    __tablename__ = "fsp_achievements"
    __table_args__ = (UniqueConstraint("user_id", "external_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.user_id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(300))
    discipline: Mapped[str | None] = mapped_column(String(200))
    level: Mapped[str | None] = mapped_column(String(32))
    result: Mapped[str | None] = mapped_column(String(32))
    place: Mapped[int | None] = mapped_column(Integer)
    team: Mapped[str | None] = mapped_column(String(200))
    event_date: Mapped[date | None] = mapped_column(Date)
    url: Mapped[str | None] = mapped_column(String(500))


class Consent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Журнал согласий (152-ФЗ): каждое согласие и отзыв сохраняются."""

    __tablename__ = "consents"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    type: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(32))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class OutboxEvent(Base):
    """Доменные события для других сервисов (подбор, тестирование, поиск).

    Пишутся в одной транзакции с изменением профиля. Пока брокера нет,
    потребители читают ленту через внутренний API по возрастанию ``id``;
    позже её можно транслировать в брокер без изменения производителя.
    """

    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
