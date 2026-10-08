"""Справочники, общие для сервисов: грейды, IT-специализации, отрасли.

Значения — стабильные идентификаторы в API, БД и событиях. Менять их
нельзя без миграции данных во всех сервисах.
"""

from enum import StrEnum


class Grade(StrEnum):
    INTERN = "intern"
    JUNIOR = "junior"
    MIDDLE = "middle"
    SENIOR = "senior"
    LEAD = "lead"


GRADE_TITLES = {
    Grade.INTERN: "Стажёр",
    Grade.JUNIOR: "Junior",
    Grade.MIDDLE: "Middle",
    Grade.SENIOR: "Senior",
    Grade.LEAD: "Lead",
}

GRADE_ORDER = {grade: index for index, grade in enumerate(Grade)}


def next_grade(grade: Grade) -> Grade:
    """Следующий по старшинству грейд (для Lead — он же)."""
    grades = list(Grade)
    return grades[min(GRADE_ORDER[grade] + 1, len(grades) - 1)]


class ITRole(StrEnum):
    BACKEND = "backend"
    FRONTEND = "frontend"
    FULLSTACK = "fullstack"
    MOBILE = "mobile"
    DEVOPS = "devops"
    QA = "qa"
    QA_AUTOMATION = "qa_automation"
    DATA_SCIENTIST = "data_scientist"
    ML_ENGINEER = "ml_engineer"
    DATA_ENGINEER = "data_engineer"
    DATA_ANALYST = "data_analyst"
    SYSTEM_ANALYST = "system_analyst"
    BUSINESS_ANALYST = "business_analyst"
    PRODUCT_MANAGER = "product_manager"
    PROJECT_MANAGER = "project_manager"
    DESIGNER = "designer"
    GAMEDEV = "gamedev"
    SECURITY = "security"
    EMBEDDED = "embedded"
    DBA = "dba"
    TEAM_LEAD = "team_lead"
    ARCHITECT = "architect"


ROLE_TITLES = {
    ITRole.BACKEND: "Backend-разработчик",
    ITRole.FRONTEND: "Frontend-разработчик",
    ITRole.FULLSTACK: "Fullstack-разработчик",
    ITRole.MOBILE: "Мобильный разработчик",
    ITRole.DEVOPS: "DevOps / SRE",
    ITRole.QA: "Тестировщик (QA)",
    ITRole.QA_AUTOMATION: "Автоматизатор тестирования",
    ITRole.DATA_SCIENTIST: "Data Scientist",
    ITRole.ML_ENGINEER: "ML-инженер",
    ITRole.DATA_ENGINEER: "Data Engineer",
    ITRole.DATA_ANALYST: "Аналитик данных",
    ITRole.SYSTEM_ANALYST: "Системный аналитик",
    ITRole.BUSINESS_ANALYST: "Бизнес-аналитик",
    ITRole.PRODUCT_MANAGER: "Продакт-менеджер",
    ITRole.PROJECT_MANAGER: "Проджект-менеджер",
    ITRole.DESIGNER: "UI/UX-дизайнер",
    ITRole.GAMEDEV: "Разработчик игр",
    ITRole.SECURITY: "Специалист по информационной безопасности",
    ITRole.EMBEDDED: "Embedded-разработчик",
    ITRole.DBA: "Администратор БД",
    ITRole.TEAM_LEAD: "Тимлид",
    ITRole.ARCHITECT: "Архитектор",
}


class Industry(StrEnum):
    FINTECH = "fintech"
    ECOMMERCE = "ecommerce"
    GOVTECH = "govtech"
    TELECOM = "telecom"
    HEALTHTECH = "healthtech"
    EDTECH = "edtech"
    GAMEDEV = "gamedev"
    MEDIA = "media"
    LOGISTICS = "logistics"
    INDUSTRY = "industry"
    ENERGY = "energy"
    CYBERSECURITY = "cybersecurity"
    AI = "ai"
    TRAVEL = "travel"
    REAL_ESTATE = "real_estate"
    OUTSOURCE = "outsource"
    OTHER = "other"


INDUSTRY_TITLES = {
    Industry.FINTECH: "Финтех и банки",
    Industry.ECOMMERCE: "E-commerce и ритейл",
    Industry.GOVTECH: "Госсектор (GovTech)",
    Industry.TELECOM: "Телеком",
    Industry.HEALTHTECH: "Медицина (HealthTech)",
    Industry.EDTECH: "Образование (EdTech)",
    Industry.GAMEDEV: "Игры",
    Industry.MEDIA: "Медиа и развлечения",
    Industry.LOGISTICS: "Логистика и транспорт",
    Industry.INDUSTRY: "Промышленность",
    Industry.ENERGY: "Энергетика",
    Industry.CYBERSECURITY: "Информационная безопасность",
    Industry.AI: "Искусственный интеллект",
    Industry.TRAVEL: "Путешествия",
    Industry.REAL_ESTATE: "Недвижимость (PropTech)",
    Industry.OUTSOURCE: "Аутсорс и заказная разработка",
    Industry.OTHER: "Другое",
}


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    PROJECT = "project"
    INTERNSHIP = "internship"


EMPLOYMENT_TYPE_TITLES = {
    EmploymentType.FULL_TIME: "Полная занятость",
    EmploymentType.PART_TIME: "Частичная занятость",
    EmploymentType.PROJECT: "Проектная работа",
    EmploymentType.INTERNSHIP: "Стажировка",
}


class WorkFormat(StrEnum):
    OFFICE = "office"
    REMOTE = "remote"
    HYBRID = "hybrid"


WORK_FORMAT_TITLES = {
    WorkFormat.OFFICE: "Офис",
    WorkFormat.REMOTE: "Удалённо",
    WorkFormat.HYBRID: "Гибрид",
}
