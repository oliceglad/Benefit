"""Схемы поиска и подбора кандидатов."""

import uuid
from datetime import datetime
from typing import Any, Literal

from benefit_common.dictionaries import Grade, Industry, ITRole, WorkFormat
from benefit_common.skills import normalize_skill
from pydantic import BaseModel, Field, field_validator


class Category(BaseModel):
    specialization: ITRole | None
    grade: Grade | None
    grade_status: str
    industry: Industry | None
    verified_percent: float | None
    test_title: str | None


class Actuality(BaseModel):
    status: str
    last_active_at: datetime
    days_since_active: int
    tasks_passed: int = 0
    tasks_submitted: int = 0
    employer_tests_completed: int = 0


class CandidateCard(BaseModel):
    """Карточка кандидата в поиске и подборке (без контактов)."""

    user_id: uuid.UUID
    full_name: str
    headline: str | None
    city: str | None
    relocation_ready: bool
    job_search_status: str
    roles: list[ITRole]
    category: Category
    skills: list[dict[str, Any]]
    # Уровни навыков, подтверждённые тестами (английский, SQL, Git…).
    verified_skills: list[dict[str, Any]] = Field(default_factory=list)
    experience_months: int
    work_formats: list[str]
    salary_from: int | None
    salary_currency: str | None
    fsp_count: int
    fsp_achievements: list[dict[str, Any]]
    actuality: Actuality
    has_photo: bool


class CategoryCount(BaseModel):
    """Категория (специализация + грейд + подтверждение) и число кандидатов."""

    specialization: ITRole | None
    grade: Grade | None
    grade_status: str
    count: int
    best_score: int | None = None
    avg_score: int | None = None
    # Чем категория интересна для потребности.
    hint: str | None = None


class SearchPage(BaseModel):
    total: int
    items: list[CandidateCard]
    categories: list[CategoryCount]


class ScorePart(BaseModel):
    """Компонент оценки: сколько баллов набрано из возможных."""

    component: str
    title: str
    points: float
    max_points: float


class RelatedSkill(BaseModel):
    required: str
    has: str


class MatchedCandidate(BaseModel):
    score: int
    # excellent — 80+, good — 65+, partial — ниже.
    fit: Literal["excellent", "good", "partial"]
    reasons: list[str]
    warnings: list[str]
    breakdown: list[ScorePart]
    matched_skills: list[str]
    related_skills: list[RelatedSkill]
    missing_skills: list[str]
    # Уже был контакт: invitation:pending|accepted|declined, application:<статус>.
    contact_status: str | None
    feedback: Literal["like", "dislike"] | None
    candidate: CandidateCard


class SimilarCandidate(BaseModel):
    similarity: int
    shared_skills: list[str]
    candidate: CandidateCard


class MatchCriteria(BaseModel):
    """Критерии подбора (из потребности работодателя)."""

    specialization: ITRole
    grade: Grade
    required_skills: list[str] = Field(default_factory=list)
    optional_skills: list[str] = Field(default_factory=list)
    title: str | None = None
    team_description: str | None = None
    industry: Industry | None = None
    work_formats: list[WorkFormat] = Field(default_factory=list)
    city: str | None = None
    salary_to: int | None = None
    currency: str = "RUB"

    # Жёсткие фильтры (исключают кандидата), остальное влияет на порядок.
    require_confirmed_grade: bool = False
    strict_skills: bool = Field(
        default=False, description="Все обязательные навыки должны быть у кандидата"
    )
    grade_tolerance: int = Field(
        default=1, ge=0, le=4, description="Допустимое отклонение грейда, ступеней"
    )
    min_experience_months: int | None = Field(default=None, ge=0)
    hard_budget: bool = Field(
        default=False, description="Исключать кандидатов с ожиданиями выше бюджета"
    )
    strict_format: bool = Field(
        default=False, description="Исключать кандидатов с другим форматом работы"
    )

    # Обратная связь работодателя по этой потребности.
    liked_ids: list[uuid.UUID] = Field(default_factory=list)
    disliked_ids: list[uuid.UUID] = Field(default_factory=list)
    # С кем уже был контакт: user_id -> статус.
    contacted: dict[uuid.UUID, str] = Field(default_factory=dict)
    hide_contacted: bool = False

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @field_validator("required_skills", "optional_skills")
    @classmethod
    def _normalize(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(normalize_skill(v) for v in value))


class Suggestion(BaseModel):
    """Какое требование ослабить, чтобы найти больше кандидатов."""

    text: str
    extra_candidates: int


class MatchResult(BaseModel):
    total: int
    categories: list[CategoryCount]
    candidates: list[MatchedCandidate]
    # Сколько кандидатов отсеяно и почему (код причины -> число).
    excluded: dict[str, int]
    suggestions: list[Suggestion]
    # Ключевые слова из описания потребности (для близости опыта).
    keywords: list[str]
