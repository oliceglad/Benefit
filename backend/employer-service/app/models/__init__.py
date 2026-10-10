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

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
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


class VerificationStatus(StrEnum):
    """Проверка компании.

    * ``unverified`` — не проверялась (или изменились ИНН / сайт);
    * ``registry_confirmed`` — компания действует по ЕГРЮЛ/ЕГРИП, но связь
      работодателя с ней не доказана: ждёт модератора;
    * ``verified`` — проверенный работодатель (автоматически или модератором);
    * ``rejected`` — ИНН нет в реестре, компания ликвидирована или
      модератор отказал.
    """

    UNVERIFIED = "unverified"
    REGISTRY_CONFIRMED = "registry_confirmed"
    VERIFIED = "verified"
    REJECTED = "rejected"


VERIFICATION_TITLES = {
    VerificationStatus.UNVERIFIED: "Не проверена",
    VerificationStatus.REGISTRY_CONFIRMED: "Найдена в ЕГРЮЛ, ожидает проверки",
    VerificationStatus.VERIFIED: "Проверенный работодатель",
    VerificationStatus.REJECTED: "Проверка не пройдена",
}


class NeedStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class VacancyStatus(StrEnum):
    """Жизненный цикл вакансии.

    * ``draft`` — черновик, кандидаты не видят;
    * ``published`` — в каталоге, на неё откликаются;
    * ``closed`` — набор закрыт (можно открыть снова);
    * ``archived`` — в архиве: скрыта из списков, не редактируется,
      восстанавливается в черновик.
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    ARCHIVED = "archived"


class SalaryType(StrEnum):
    """Налоговый режим зарплаты."""

    GROSS = "gross"  # до вычета НДФЛ
    NET = "net"  # на руки


def _json_list() -> Any:
    return mapped_column(JSONB, default=list, server_default="[]")


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    # Пользователь-работодатель, которому принадлежит профиль.
    owner_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(200))
    legal_name: Mapped[str | None] = mapped_column(String(300))
    inn: Mapped[str | None] = mapped_column(String(12), index=True)
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

    # Проверка компании (статус выставляет только сервер).
    verification_status: Mapped[str] = mapped_column(
        String(24),
        default=VerificationStatus.UNVERIFIED,
        server_default=VerificationStatus.UNVERIFIED.value,
    )
    # Результаты проверок: [{code, passed, message}].
    verification_checks: Mapped[list[dict[str, Any]]] = _json_list()
    # Данные из ЕГРЮЛ/ЕГРИП на момент последней проверки.
    registry_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # auto — по открытым источникам, moderator — решение модератора.
    verified_by: Mapped[str | None] = mapped_column(String(16))
    verification_note: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def verification(self) -> dict[str, Any]:
        """Блок проверки для ответов API (публичная схема берёт часть полей)."""
        status = VerificationStatus(self.verification_status)
        return {
            "status": status,
            "title": VERIFICATION_TITLES[status],
            "is_verified": status == VerificationStatus.VERIFIED,
            "verified_at": self.verified_at,
            "registry": self.registry_data,
            "verified_by": self.verified_by,
            "note": self.verification_note,
            "checked_at": self.checked_at,
            "checks": self.verification_checks or [],
        }


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
    """Отметка работодателя по кандидату в подборке потребности или вакансии:
    «подходит» поднимает похожих кандидатов, «не подходит» убирает кандидата
    и опускает похожих."""

    __tablename__ = "need_feedback"
    __table_args__ = (
        UniqueConstraint("need_id", "candidate_id"),
        UniqueConstraint("vacancy_id", "candidate_id"),
        CheckConstraint("num_nonnulls(need_id, vacancy_id) = 1", name="one_target"),
    )

    need_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hiring_needs.id", ondelete="CASCADE"), index=True
    )
    vacancy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), index=True
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
    required_skills: Mapped[list[str]] = _json_list()
    optional_skills: Mapped[list[str]] = _json_list()
    # Обязанности — отдельными пунктами.
    responsibilities: Mapped[list[str]] = _json_list()
    salary_from: Mapped[int | None]
    salary_to: Mapped[int | None]
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    salary_type: Mapped[str] = mapped_column(
        String(8), default=SalaryType.GROSS, server_default=SalaryType.GROSS.value
    )
    work_format: Mapped[str | None] = mapped_column(String(16))
    employment_type: Mapped[str | None] = mapped_column(String(16))
    city: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(16), default=VacancyStatus.DRAFT)
    # Первая публикация (дата для каталога).
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Настройки подбора (жёсткие фильтры): см. schemas.MatchingSettings.
    matching_settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    # Растёт при каждом изменении требований, влияющих на подбор.
    matching_version: Mapped[int] = mapped_column(default=1, server_default="1")

    match_snapshot: Mapped["VacancyMatchSnapshot | None"] = relationship(
        lazy="selectin", viewonly=True
    )

    @property
    def matching(self) -> dict[str, Any]:
        return self.matching_settings or {}

    @property
    def matching_state(self) -> dict[str, Any]:
        """Актуальность сохранённой подборки для фронтенда."""
        snapshot = self.match_snapshot
        return {
            "version": self.matching_version,
            "computed_version": snapshot.version if snapshot else None,
            "computed_at": snapshot.computed_at if snapshot else None,
            # Требования изменились после последнего подбора: список,
            # который видел работодатель, устарел.
            "requirements_changed": snapshot is not None
            and snapshot.version != self.matching_version,
        }

    @property
    def publish_blockers(self) -> list[str]:
        """Чего не хватает для публикации (коды полей)."""
        blockers = []
        if not self.required_skills:
            blockers.append("required_skills")
        if not self.responsibilities:
            blockers.append("responsibilities")
        return blockers

    company: Mapped[Company] = relationship()


class VacancyMatchSnapshot(Base):
    """Последний подбор кандидатов по вакансии.

    Хранит до 100 лучших кандидатов, хэш критериев, по которым они подобраны,
    и разницу с предыдущим подбором после изменения требований.
    """

    __tablename__ = "vacancy_match_snapshots"

    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), primary_key=True
    )
    # Версия требований вакансии, для которой посчитан подбор.
    version: Mapped[int]
    criteria_hash: Mapped[str] = mapped_column(String(64))
    feedback_hash: Mapped[str] = mapped_column(String(64))
    # Почему пересчитан: initial, criteria, feedback, refresh, expired.
    reason: Mapped[str] = mapped_column(String(16))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # После изменения требований: {from_version, to_version, added, removed}.
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


__all__ = [
    "Base",
    "Company",
    "VerificationStatus",
    "CompanySize",
    "FeedbackVerdict",
    "NeedFeedback",
    "HiringNeed",
    "NeedStatus",
    "SalaryType",
    "Vacancy",
    "VacancyMatchSnapshot",
    "VacancyStatus",
]
