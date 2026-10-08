"""ORM-модели matching-service.

``CandidateIndex`` — денормализованная копия опубликованных профилей для
поиска и подбора. Источник истины — candidate-service: индекс
перестраивается по его ленте событий. В индексе только то, что
работодатель вправе видеть (с учётом приватности), контактов нет.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CandidateIndex(Base):
    __tablename__ = "candidate_index"
    __table_args__ = (
        Index("ix_candidate_index_skills", "skills", postgresql_using="gin"),
        Index("ix_candidate_index_roles", "roles", postgresql_using="gin"),
        Index("ix_candidate_index_search", "search_vector", postgresql_using="gin"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(300))
    headline: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    relocation_ready: Mapped[bool] = mapped_column(default=False)
    job_search_status: Mapped[str] = mapped_column(String(16))
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    # Категория (как её видит работодатель).
    specialization: Mapped[str | None] = mapped_column(String(32))
    grade: Mapped[str | None] = mapped_column(String(16))
    grade_status: Mapped[str] = mapped_column(String(16))
    verified_percent: Mapped[float | None]
    test_title: Mapped[str | None] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(32))
    # Навыки в нижнем регистре — для фильтров; skills_display — для карточки.
    skills: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    skills_display: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    # Подтверждение навыков опытом: {"python": {"months": 40, "last_used": "2026-10"}}
    # — сколько месяцев навык был в стеке мест работы и когда в последний раз.
    skill_experience: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    experience_months: Mapped[int]
    work_formats: Mapped[list[str]] = mapped_column(ARRAY(String(16)))
    employment_types: Mapped[list[str]] = mapped_column(ARRAY(String(16)))
    salary_from: Mapped[int | None]
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    fsp_count: Mapped[int]
    fsp_achievements: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activity: Mapped[dict[str, Any]] = mapped_column(JSONB)
    has_photo: Mapped[bool]
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    about: Mapped[str | None] = mapped_column(Text)
    search_vector: Mapped[Any] = mapped_column(TSVECTOR)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConsumerOffset(Base):
    """Позиция в ленте событий источника (для продолжения после рестарта)."""

    __tablename__ = "consumer_offsets"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_event_id: Mapped[int] = mapped_column(BigInteger, default=0)


__all__ = ["Base", "CandidateIndex", "ConsumerOffset"]
