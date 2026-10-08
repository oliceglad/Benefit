"""Справочники профиля IT-кандидата.

Значения перечислений — стабильные идентификаторы: их используют фронтенд,
будущие сервисы тестирования и подбора. Подписи — только для отображения.
"""

from enum import StrEnum

from benefit_common.dictionaries import (
    EMPLOYMENT_TYPE_TITLES,
    GRADE_ORDER,
    GRADE_TITLES,
    INDUSTRY_TITLES,
    ROLE_TITLES,
    WORK_FORMAT_TITLES,
    EmploymentType,
    Grade,
    Industry,
    ITRole,
    WorkFormat,
)
from benefit_common.skills import (
    SKILL_CATALOG,
    find_skill,
    normalize_skill,
    suggest_skills,
)

__all__ = [
    "EMPLOYMENT_TYPE_TITLES",
    "SKILL_CATALOG",
    "WORK_FORMAT_TITLES",
    "EmploymentType",
    "WorkFormat",
    "find_skill",
    "normalize_skill",
    "suggest_skills",
    "GRADE_ORDER",
    "GRADE_TITLES",
    "INDUSTRY_TITLES",
    "ROLE_TITLES",
    "Grade",
    "ITRole",
    "Industry",
]


class SkillLevel(StrEnum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


SKILL_LEVEL_TITLES = {
    SkillLevel.BASIC: "Базовый",
    SkillLevel.INTERMEDIATE: "Уверенный",
    SkillLevel.ADVANCED: "Продвинутый",
    SkillLevel.EXPERT: "Эксперт",
}


class LanguageLevel(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"
    NATIVE = "native"


LANGUAGE_LEVEL_TITLES = {
    LanguageLevel.A1: "A1 — Начальный",
    LanguageLevel.A2: "A2 — Элементарный",
    LanguageLevel.B1: "B1 — Средний",
    LanguageLevel.B2: "B2 — Средне-продвинутый",
    LanguageLevel.C1: "C1 — Продвинутый",
    LanguageLevel.C2: "C2 — В совершенстве",
    LanguageLevel.NATIVE: "Родной",
}

LANGUAGES = [
    "Русский",
    "Английский",
    "Немецкий",
    "Французский",
    "Испанский",
    "Китайский",
    "Японский",
    "Корейский",
    "Итальянский",
    "Турецкий",
    "Арабский",
    "Казахский",
    "Татарский",
]


class JobSearchStatus(StrEnum):
    ACTIVE = "active"
    OPEN = "open"
    NOT_LOOKING = "not_looking"


JOB_SEARCH_STATUS_TITLES = {
    JobSearchStatus.ACTIVE: "Активно ищу работу",
    JobSearchStatus.OPEN: "Рассматриваю предложения",
    JobSearchStatus.NOT_LOOKING: "Не ищу работу",
}


class EducationLevel(StrEnum):
    SECONDARY_SPECIAL = "secondary_special"
    INCOMPLETE_HIGHER = "incomplete_higher"
    BACHELOR = "bachelor"
    SPECIALIST = "specialist"
    MASTER = "master"
    PHD = "phd"


EDUCATION_LEVEL_TITLES = {
    EducationLevel.SECONDARY_SPECIAL: "Среднее специальное",
    EducationLevel.INCOMPLETE_HIGHER: "Неоконченное высшее",
    EducationLevel.BACHELOR: "Бакалавр",
    EducationLevel.SPECIALIST: "Специалист",
    EducationLevel.MASTER: "Магистр",
    EducationLevel.PHD: "Кандидат / доктор наук",
}


class LinkType(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"
    LINKEDIN = "linkedin"
    HABR = "habr"
    PORTFOLIO = "portfolio"
    OTHER = "other"


LINK_TYPE_TITLES = {
    LinkType.GITHUB: "GitHub",
    LinkType.GITLAB: "GitLab",
    LinkType.LINKEDIN: "LinkedIn",
    LinkType.HABR: "Хабр Карьера",
    LinkType.PORTFOLIO: "Портфолио",
    LinkType.OTHER: "Другое",
}

SOFT_SKILLS = [
    "Работа в команде",
    "Коммуникабельность",
    "Ответственность",
    "Самоорганизация",
    "Тайм-менеджмент",
    "Обучаемость",
    "Критическое мышление",
    "Аналитическое мышление",
    "Решение проблем",
    "Лидерство",
    "Наставничество",
    "Стрессоустойчивость",
    "Адаптивность",
    "Инициативность",
    "Публичные выступления",
    "Ведение переговоров",
    "Управление конфликтами",
    "Эмоциональный интеллект",
    "Внимание к деталям",
    "Креативность",
    "Клиентоориентированность",
    "Умение давать и принимать обратную связь",
]
