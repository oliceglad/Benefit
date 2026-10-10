"""Схемы профиля кандидата."""

import re
import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Self

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

from app.domain.dictionaries import (
    EducationLevel,
    EmploymentType,
    Grade,
    Industry,
    ITRole,
    JobSearchStatus,
    LanguageLevel,
    LinkType,
    SkillLevel,
    WorkFormat,
    normalize_skill,
)


def _str(max_length: int, min_length: int = 1) -> Any:
    return Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=min_length, max_length=max_length
        ),
    ]


def _first_of_month(value: date) -> date:
    return value.replace(day=1)


Name = _str(100)
ShortText = _str(200)
LongText = _str(4000)
AchievementText = _str(500)
SoftSkillName = _str(64)
Currency = _str(3, 3)
Month = Annotated[date, AfterValidator(_first_of_month)]
SkillName = Annotated[_str(64), AfterValidator(normalize_skill)]
_http_url = TypeAdapter(HttpUrl)


def _check_url(value: str) -> str:
    return str(_http_url.validate_python(value))


Url = Annotated[str, StringConstraints(max_length=500), AfterValidator(_check_url)]


def _unique[T](items: list[T], key: Any = None) -> list[T]:
    seen: set[Any] = set()
    result = []
    for item in items:
        marker = key(item) if key else item
        if marker not in seen:
            seen.add(marker)
            result.append(item)
    return result


class Skill(BaseModel):
    name: SkillName
    level: SkillLevel | None = None
    years: float | None = Field(default=None, ge=0, le=50)


class Language(BaseModel):
    language: Name
    level: LanguageLevel


class VerifiedSkillLevel(BaseModel):
    id: str
    title: str


class VerifiedSkill(BaseModel):
    """Уровень навыка, подтверждённый тестом платформы (английский, SQL…)."""

    skill: str
    level: VerifiedSkillLevel
    verified_at: datetime
    valid_until: datetime
    percent: float
    test_title: str


class Link(BaseModel):
    type: LinkType
    url: Url


class Experience(BaseModel):
    company: ShortText
    position: ShortText
    start_date: Month
    # None — работает по настоящее время.
    end_date: Month | None = None
    city: Name | None = None
    description: LongText | None = None
    achievements: list[AchievementText] = Field(default_factory=list, max_length=20)
    technologies: list[SkillName] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.start_date > date.today():
            raise ValueError("Дата начала работы не может быть в будущем")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("Дата окончания раньше даты начала")
        self.technologies = _unique(self.technologies)
        return self


class Education(BaseModel):
    institution: ShortText
    level: EducationLevel | None = None
    faculty: ShortText | None = None
    specialization: ShortText | None = None
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)


class Course(BaseModel):
    name: ShortText
    organization: ShortText | None = None
    year: int | None = Field(default=None, ge=1950, le=2100)
    url: Url | None = None


class Project(BaseModel):
    name: ShortText
    role: ShortText | None = None
    description: LongText | None = None
    url: Url | None = None
    technologies: list[SkillName] = Field(default_factory=list, max_length=50)


class PrivacySettings(BaseModel):
    """Что из опубликованного профиля видно работодателям.

    Контакты здесь не настраиваются: работодатель видит их только после
    того, как кандидат принял его приглашение или сам откликнулся.
    """

    show_birth_date: bool = True
    show_photo: bool = True
    show_salary: bool = True
    show_fsp_achievements: bool = True
    # Скрыть название текущей компании (как на hh.ru), чтобы её не увидел
    # нынешний работодатель.
    hide_current_company: bool = False


PHONE_RE = re.compile(r"^\+?\d{10,15}$")
TELEGRAM_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


class ProfileUpdate(BaseModel):
    """Частичное обновление: передаются только изменяемые поля.

    Фронтенд может сохранять профиль по шагам онбординга.
    """

    model_config = ConfigDict(extra="forbid")

    last_name: Name | None = None
    first_name: Name | None = None
    middle_name: Name | None = None
    birth_date: date | None = None
    city: Name | None = None
    relocation_ready: bool = False

    phone: str | None = None
    contact_email: EmailStr | None = None
    telegram: str | None = None
    links: list[Link] = Field(default_factory=list, max_length=10)

    headline: ShortText | None = Field(
        default=None, description="Желаемая должность, например «Python-разработчик»"
    )
    about: LongText | None = None
    grade: Grade | None = None
    industry: Industry | None = None
    roles: list[ITRole] = Field(default_factory=list, max_length=5)
    skills: list[Skill] = Field(default_factory=list, max_length=100)
    soft_skills: list[SoftSkillName] = Field(default_factory=list, max_length=30)
    languages: list[Language] = Field(default_factory=list, max_length=15)

    experience: list[Experience] = Field(default_factory=list, max_length=50)
    education: list[Education] = Field(default_factory=list, max_length=20)
    courses: list[Course] = Field(default_factory=list, max_length=50)
    projects: list[Project] = Field(default_factory=list, max_length=30)

    salary_from: int | None = Field(default=None, ge=0, le=100_000_000)
    salary_currency: Currency = "RUB"
    employment_types: list[EmploymentType] = Field(default_factory=list)
    work_formats: list[WorkFormat] = Field(default_factory=list)
    job_search_status: JobSearchStatus = JobSearchStatus.ACTIVE

    privacy: PrivacySettings | None = None

    @field_validator("birth_date")
    @classmethod
    def _check_age(cls, value: date | None) -> date | None:
        if value is not None and not 14 <= age_on(value, date.today()) <= 100:
            raise ValueError("Возраст должен быть от 14 до 100 лет")
        return value

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        if not value:
            return None
        digits = re.sub(r"[\s()\-]", "", value)
        if digits.startswith("8") and len(digits) == 11:
            digits = "+7" + digits[1:]
        if not PHONE_RE.match(digits):
            raise ValueError("Некорректный номер телефона")
        return digits if digits.startswith("+") else f"+{digits}"

    @field_validator("telegram")
    @classmethod
    def _normalize_telegram(cls, value: str | None) -> str | None:
        if not value:
            return None
        handle = re.sub(r"^(https?://)?(t\.me/|@)", "", value.strip())
        if not TELEGRAM_RE.match(handle):
            raise ValueError("Некорректный username в Telegram")
        return f"@{handle}"

    @field_validator("contact_email")
    @classmethod
    def _lower_email(cls, value: str | None) -> str | None:
        return value.lower() if value else None

    @field_validator("skills")
    @classmethod
    def _unique_skills(cls, value: list[Skill]) -> list[Skill]:
        return _unique(value, key=lambda s: s.name.lower())

    @field_validator("roles", "employment_types", "work_formats")
    @classmethod
    def _unique_values(cls, value: list[Any]) -> list[Any]:
        return _unique(value)

    @field_validator("soft_skills")
    @classmethod
    def _unique_soft_skills(cls, value: list[str]) -> list[str]:
        return _unique(value, key=str.lower)

    @field_validator("languages")
    @classmethod
    def _unique_languages(cls, value: list[Language]) -> list[Language]:
        return _unique(value, key=lambda lang: lang.language.lower())


def age_on(birth_date: date, today: date) -> int:
    before_birthday = (today.month, today.day) < (birth_date.month, birth_date.day)
    return today.year - birth_date.year - before_birthday


class FspAchievementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    external_id: str
    event: str
    discipline: str | None
    level: str | None
    result: str | None
    place: int | None
    team: str | None
    event_date: date | None
    url: str | None


class FspInfo(BaseModel):
    linked: bool
    participant_id: str | None
    synced_at: datetime | None
    achievements: list[FspAchievementResponse]


class OnboardingStep(BaseModel):
    id: str
    title: str
    completed: bool


class Completeness(BaseModel):
    percent: int
    can_publish: bool
    missing_required: list[str]
    missing_recommended: list[str]
    onboarding_completed: bool
    next_step: str | None
    steps: list[OnboardingStep]


class GradeStatus(StrEnum):
    CONFIRMED = "confirmed"
    NOT_CONFIRMED = "not_confirmed"


class Category(BaseModel):
    """Категория кандидата, видимая работодателю: отрасль, специализация
    и грейд со статусом подтверждения.

    Если тест показал грейд ниже заявленного, показывается заявленный грейд
    со статусом «не подтверждён» — низкий результат работодателю не виден.
    """

    industry: Industry | None
    specialization: ITRole | None
    grade: Grade | None
    grade_status: GradeStatus
    verified_at: datetime | None = None
    test_title: str | None = None
    percent: float | None = None


class ActualityStatus(StrEnum):
    ACTIVE = "active"
    RECENT = "recent"
    STALE = "stale"


class Actuality(BaseModel):
    """Актуальность профиля: насколько недавно кандидат проявлял активность
    (обновлял профиль, проходил тест, решал задания работодателей)."""

    status: ActualityStatus
    last_active_at: datetime
    # Задания работодателей за последние 180 дней.
    tasks_assigned: int
    tasks_submitted: int
    tasks_passed: int
    tasks_failed: int
    tasks_expired: int
    # Тесты, присланные работодателями.
    employer_tests_completed: int


class ProfileData(BaseModel):
    """Поля профиля, общие для всех представлений."""

    last_name: str | None
    first_name: str | None
    middle_name: str | None
    city: str | None
    relocation_ready: bool
    headline: str | None
    about: str | None
    grade: Grade | None
    industry: Industry | None
    category: Category
    roles: list[ITRole]
    skills: list[Skill]
    soft_skills: list[str]
    languages: list[Language]
    # Подтверждённые тестами уровни навыков (действующие).
    verified_skills: list[VerifiedSkill]
    experience: list[Experience]
    education: list[Education]
    courses: list[Course]
    projects: list[Project]
    links: list[Link]
    employment_types: list[EmploymentType]
    work_formats: list[WorkFormat]
    job_search_status: JobSearchStatus
    total_experience_months: int


class ProfileResponse(ProfileData):
    """Профиль глазами владельца: все поля и служебная информация."""

    user_id: uuid.UUID
    status: str
    published_at: datetime | None
    # Сырой результат тестирования — только владельцу профиля.
    verified_grade: Grade | None
    verified_specialization: ITRole | None
    grade_verified_at: datetime | None
    birth_date: date | None
    age: int | None
    phone: str | None
    contact_email: str | None
    telegram: str | None
    salary_from: int | None
    salary_currency: str
    privacy: PrivacySettings
    has_photo: bool
    actuality: Actuality
    fsp: FspInfo
    completeness: Completeness
    created_at: datetime
    updated_at: datetime


class ContactAccess(StrEnum):
    # Кандидат принял приглашение этого работодателя или откликнулся сам.
    GRANTED = "granted"
    HIDDEN = "hidden"


class PublicProfileResponse(ProfileData):
    """Профиль глазами работодателя (с учётом приватности)."""

    user_id: uuid.UUID
    contact_access: ContactAccess
    published_at: datetime | None
    age: int | None
    phone: str | None
    contact_email: str | None
    telegram: str | None
    salary_from: int | None
    salary_currency: str | None
    has_photo: bool
    actuality: Actuality
    fsp_achievements: list[FspAchievementResponse]


class ResumeImportResponse(BaseModel):
    """Данные, распознанные в PDF. Это подсказки для формы, а не готовый
    профиль: пользователь проверяет их перед сохранением."""

    draft: dict[str, Any]
    warnings: list[str]
    applied: bool
    applied_fields: list[str] = []
