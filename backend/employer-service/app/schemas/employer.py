"""Схемы профиля компании, потребностей и вакансий."""

import re
import uuid
from datetime import datetime
from typing import Annotated, Any, Self

from benefit_common.dictionaries import (
    EmploymentType,
    Grade,
    Industry,
    ITRole,
    WorkFormat,
)
from benefit_common.skills import normalize_skill
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.models import CompanySize, FeedbackVerdict, NeedStatus, VacancyStatus


def _str(max_length: int, min_length: int = 1) -> Any:
    return Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=min_length, max_length=max_length
        ),
    ]


Name = _str(200)
LongText = _str(8000)
SkillName = Annotated[_str(64), AfterValidator(normalize_skill)]
_http_url = TypeAdapter(HttpUrl)
Url = Annotated[
    str,
    StringConstraints(max_length=300),
    AfterValidator(lambda v: str(_http_url.validate_python(v))),
]

INN_WEIGHTS_10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
INN_WEIGHTS_12_1 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
INN_WEIGHTS_12_2 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _checksum(digits: list[int], weights: tuple[int, ...]) -> int:
    return sum(d * w for d, w in zip(digits, weights, strict=False)) % 11 % 10


def is_valid_inn(value: str) -> bool:
    """ИНН организации (10 цифр) или ИП (12 цифр) с контрольными цифрами."""
    if not re.fullmatch(r"\d{10}|\d{12}", value):
        return False
    digits = [int(c) for c in value]
    if len(digits) == 10:
        return _checksum(digits, INN_WEIGHTS_10) == digits[9]
    return (
        _checksum(digits, INN_WEIGHTS_12_1) == digits[10]
        and _checksum(digits, INN_WEIGHTS_12_2) == digits[11]
    )


def _unique_skills(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value.lower() not in seen:
            seen.add(value.lower())
            result.append(value)
    return result


class SalaryRange(BaseModel):
    salary_from: int | None = Field(default=None, ge=0, le=100_000_000)
    salary_to: int | None = Field(default=None, ge=0, le=100_000_000)
    currency: str = Field(default="RUB", pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def _check_salary(self) -> Self:
        if (
            self.salary_from is not None
            and self.salary_to is not None
            and self.salary_from > self.salary_to
        ):
            raise ValueError("Зарплата «от» больше, чем «до»")
        return self


# --- Компания ---------------------------------------------------------------


class CompanyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    legal_name: _str(300) | None = None
    inn: str | None = None
    industry: Industry
    description: LongText
    website: Url | None = None
    city: _str(100) | None = None
    size: CompanySize | None = None
    tech_stack: list[SkillName] = Field(default_factory=list, max_length=50)
    contact_name: Name | None = None
    contact_email: EmailStr | None = None
    contact_phone: _str(32) | None = None
    telegram: _str(64) | None = None

    @field_validator("inn")
    @classmethod
    def _check_inn(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not is_valid_inn(value):
            raise ValueError("Некорректный ИНН")
        return value

    @field_validator("tech_stack")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        return _unique_skills(value)


class CompanyResponse(CompanyIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --- Потребность ----------------------------------------------------------------


class NeedIn(SalaryRange):
    """Кого ищет работодатель: по этому описанию строится подборка."""

    model_config = ConfigDict(extra="forbid")

    title: Name = Field(description="Например, «Python-разработчик в команду платежей»")
    team_description: LongText = Field(description="Чем занимается команда")
    specialization: ITRole
    grade: Grade
    required_skills: list[SkillName] = Field(min_length=1, max_length=30)
    optional_skills: list[SkillName] = Field(default_factory=list, max_length=30)
    work_formats: list[WorkFormat] = Field(default_factory=list)
    city: _str(100) | None = None
    headcount: int = Field(default=1, ge=1, le=100)

    # Жёсткие требования: кандидаты, не прошедшие их, в подборку не попадают.
    require_confirmed_grade: bool = False
    strict_skills: bool = Field(
        default=False, description="Все обязательные навыки (близкие не в счёт)"
    )
    grade_tolerance: int = Field(
        default=1, ge=0, le=4, description="Допустимое отклонение грейда, ступеней"
    )
    min_experience_months: int | None = Field(default=None, ge=0, le=600)
    hard_budget: bool = Field(
        default=False, description="Исключать ожидания выше salary_to"
    )
    strict_format: bool = Field(
        default=False, description="Исключать кандидатов с другим форматом работы"
    )

    @field_validator("required_skills", "optional_skills")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        return _unique_skills(value)


class NeedResponse(NeedIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    status: NeedStatus
    created_at: datetime
    updated_at: datetime


class NeedStatusUpdate(BaseModel):
    status: NeedStatus


# --- Вакансия ---------------------------------------------------------------------


class VacancyIn(SalaryRange):
    model_config = ConfigDict(extra="forbid")

    title: Name
    description: LongText
    specialization: ITRole
    grade: Grade
    skills: list[SkillName] = Field(default_factory=list, max_length=30)
    work_format: WorkFormat | None = None
    employment_type: EmploymentType | None = None
    city: _str(100) | None = None
    need_id: uuid.UUID | None = None

    @field_validator("skills")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        return _unique_skills(value)


class CompanyBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    industry: Industry
    city: str | None
    website: str | None


class VacancyResponse(VacancyIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company: CompanyBrief
    owner_id: uuid.UUID
    status: VacancyStatus
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VacancyStatusUpdate(BaseModel):
    status: VacancyStatus


class VacancyPage(BaseModel):
    total: int
    items: list[VacancyResponse]


# --- Отметки по кандидатам ---


class FeedbackIn(BaseModel):
    verdict: FeedbackVerdict
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(FeedbackIn):
    model_config = ConfigDict(from_attributes=True)

    candidate_id: uuid.UUID
    updated_at: datetime


# --- Подборка -----------------------------------------------------------------------


class MatchResponse(BaseModel):
    """Подборка по потребности (из matching-service)."""

    need_id: uuid.UUID
    total: int
    categories: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    excluded: dict[str, int] = Field(default_factory=dict)
    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
