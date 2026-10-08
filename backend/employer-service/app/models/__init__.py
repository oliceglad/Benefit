"""ORM-модели employer-service.

* ``Company`` — профиль компании работодателя;
* ``HiringNeed`` — потребность: кого ищем, чем занимается команда, стек,
  специализация и грейд; по ней строится подборка кандидатов;
* ``Vacancy`` — опубликованная вакансия (на неё откликаются кандидаты).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CompanySize(StrEnum):
    MICRO = "1-10"
    SMALL = "11-50"
    MEDIUM = "51-200"
    LARGE = "201-1000"
    ENTERPRISE = "1000+"


class NeedStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class VacancyStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


def _json_list() -> Any:
    return mapped_column(JSONB, default=list, server_default="[]")


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    # Пользователь-работодатель, которому принадлежит профиль.
    owner_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(200))
    legal_name: Mapped[str | None] = mapped_column(String(300))
    inn: Mapped[str | None] = mapped_column(String(12))
    industry: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(100))
    size: Mapped[str | None] = mapped_column(String(16))
    tech_stack: Mapped[list[str]] = _json_list()
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    telegram: Mapped[str | None] = mapped_column(String(64))


class HiringNeed(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hiring_needs"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(200))
    team_description: Mapped[str] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(32))
    grade: Mapped[str] = mapped_column(String(16))
    required_skills: Mapped[list[str]] = _json_list()
    optional_skills: Mapped[list[str]] = _json_list()
    work_formats: Mapped[list[str]] = _json_list()
    city: Mapped[str | None] = mapped_column(String(100))
    salary_from: Mapped[int | None]
    salary_to: Mapped[int | None]
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    headcount: Mapped[int] = mapped_column(default=1)
    # Жёсткие требования (исключают кандидата из подборки).
    # Только кандидаты с подтверждённым тестированием грейдом.
    require_confirmed_grade: Mapped[bool] = mapped_column(default=False)
    # Все обязательные навыки должны быть (близкие технологии не в счёт).
    strict_skills: Mapped[bool] = mapped_column(default=False, server_default="false")
    # Допустимое отклонение грейда в ступенях.
    grade_tolerance: Mapped[int] = mapped_column(default=1, server_default="1")
    min_experience_months: Mapped[int | None]
    # Бюджет как жёсткое ограничение.
    hard_budget: Mapped[bool] = mapped_column(default=False, server_default="false")
    strict_format: Mapped[bool] = mapped_column(default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(16), default=NeedStatus.ACTIVE)

    company: Mapped[Company] = relationship()


class FeedbackVerdict(StrEnum):
    LIKE = "like"
    DISLIKE = "dislike"


class NeedFeedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Отметка работодателя по кандидату в подборке: «подходит» поднимает
    похожих кандидатов, «не подходит» убирает кандидата и опускает похожих."""

    __tablename__ = "need_feedback"
    __table_args__ = (UniqueConstraint("need_id", "candidate_id"),)

    need_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hiring_needs.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID]
    verdict: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str | None] = mapped_column(Text)


class Vacancy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vacancies"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(index=True)
    need_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hiring_needs.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(32), index=True)
    grade: Mapped[str] = mapped_column(String(16))
    skills: Mapped[list[str]] = _json_list()
    salary_from: Mapped[int | None]
    salary_to: Mapped[int | None]
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    work_format: Mapped[str | None] = mapped_column(String(16))
    employment_type: Mapped[str | None] = mapped_column(String(16))
    city: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(16), default=VacancyStatus.DRAFT)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship()


__all__ = [
    "Base",
    "Company",
    "CompanySize",
    "FeedbackVerdict",
    "NeedFeedback",
    "HiringNeed",
    "NeedStatus",
    "Vacancy",
    "VacancyStatus",
]
