"""Справочники профиля IT-кандидата.

Значения перечислений — стабильные идентификаторы: их используют фронтенд,
будущие сервисы тестирования и подбора. Подписи — только для отображения.
"""

import re
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

# Каталог навыков: каноническое название -> синонимы (в нижнем регистре).
# Нормализация нужна, чтобы «питон», «python3» и «Python» были одним навыком
# для поиска и подбора вакансий.
SKILL_CATALOG: dict[str, list[str]] = {
    # Языки
    "Python": ["python3", "питон", "пайтон"],
    "Java": [],
    "Kotlin": [],
    "Go": ["golang"],
    "JavaScript": ["js", "javascript", "ecmascript", "es6"],
    "TypeScript": ["ts"],
    "C": [],
    "C++": ["cpp", "c plus plus"],
    "C#": ["csharp", "c sharp"],
    "Rust": [],
    "PHP": [],
    "Ruby": [],
    "Swift": [],
    "Objective-C": ["objc"],
    "Dart": [],
    "Scala": [],
    "R": [],
    "SQL": [],
    "Bash": ["shell", "sh"],
    "1С": ["1c", "1с:предприятие"],
    # Backend
    "FastAPI": [],
    "Django": ["django rest framework", "drf"],
    "Flask": [],
    "aiohttp": [],
    "Celery": [],
    "SQLAlchemy": [],
    "Spring": ["spring boot", "springboot", "spring framework"],
    "Hibernate": [],
    ".NET": ["dotnet", "asp.net", ".net core"],
    "Node.js": ["nodejs", "node"],
    "NestJS": ["nest.js"],
    "Express": ["express.js", "expressjs"],
    "Laravel": [],
    "Ruby on Rails": ["rails", "ror"],
    "gRPC": [],
    "REST API": ["rest", "restful", "rest api"],
    "GraphQL": [],
    "Микросервисы": ["microservices", "микросервисная архитектура"],
    # Frontend
    "HTML": ["html5"],
    "CSS": ["css3"],
    "React": ["react.js", "reactjs"],
    "Next.js": ["nextjs"],
    "Vue.js": ["vue", "vuejs", "vue 3"],
    "Nuxt": ["nuxt.js"],
    "Angular": [],
    "Svelte": [],
    "Redux": [],
    "Webpack": [],
    "Vite": [],
    "Tailwind CSS": ["tailwind"],
    "Sass": ["scss"],
    # Mobile
    "Android": [],
    "iOS": [],
    "Flutter": [],
    "React Native": [],
    "Jetpack Compose": [],
    "SwiftUI": [],
    # Базы данных
    "PostgreSQL": ["postgres", "postgre", "постгрес", "psql"],
    "MySQL": [],
    "MongoDB": ["mongo"],
    "Redis": [],
    "ClickHouse": [],
    "Elasticsearch": ["elastic", "opensearch"],
    "Oracle": [],
    "MS SQL Server": ["mssql", "sql server"],
    "Cassandra": [],
    # Очереди и интеграция
    "Kafka": ["apache kafka"],
    "RabbitMQ": ["rabbit"],
    "NATS": [],
    # DevOps
    "Docker": [],
    "Kubernetes": ["k8s", "кубернетес"],
    "Helm": [],
    "Terraform": [],
    "Ansible": [],
    "Linux": ["unix"],
    "Nginx": [],
    "CI/CD": ["ci", "cd", "ci cd"],
    "GitLab CI": [],
    "GitHub Actions": [],
    "Jenkins": [],
    "Prometheus": [],
    "Grafana": [],
    "AWS": ["amazon web services"],
    "Yandex Cloud": ["яндекс облако"],
    "Git": [],
    # Data / ML
    "Pandas": [],
    "NumPy": [],
    "scikit-learn": ["sklearn"],
    "PyTorch": ["torch"],
    "TensorFlow": [],
    "Keras": [],
    "CatBoost": [],
    "XGBoost": [],
    "LightGBM": [],
    "Machine Learning": ["ml", "машинное обучение"],
    "Deep Learning": ["dl", "глубокое обучение"],
    "NLP": [],
    "Computer Vision": ["cv", "компьютерное зрение"],
    "LLM": ["large language models"],
    "Apache Spark": ["spark", "pyspark"],
    "Airflow": ["apache airflow"],
    "Hadoop": [],
    "dbt": [],
    "Power BI": [],
    "Tableau": [],
    "Excel": [],
    "Jupyter": [],
    # QA
    "Pytest": [],
    "Selenium": [],
    "Playwright": [],
    "Cypress": [],
    "JUnit": [],
    "Postman": [],
    "Allure": [],
    "JMeter": [],
    "Ручное тестирование": ["manual testing"],
    "Автоматизация тестирования": ["test automation"],
    # Аналитика и дизайн
    "UML": [],
    "BPMN": [],
    "Jira": [],
    "Confluence": [],
    "Figma": [],
    "Adobe Photoshop": ["photoshop"],
    # Безопасность
    "Пентест": ["pentest", "penetration testing"],
    "OWASP": [],
    "SIEM": [],
    # Прочее
    "Unity": [],
    "Unreal Engine": ["ue", "ue5"],
    "Algorithms": ["алгоритмы", "алгоритмы и структуры данных"],
    "Agile": ["scrum", "kanban"],
}


def _key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


_SKILL_INDEX: dict[str, str] = {}
for _canonical, _aliases in SKILL_CATALOG.items():
    _SKILL_INDEX[_key(_canonical)] = _canonical
    for _alias in _aliases:
        _SKILL_INDEX[_key(_alias)] = _canonical


def normalize_skill(name: str) -> str:
    """Каноническое название навыка; неизвестные навыки — как ввёл пользователь."""
    cleaned = re.sub(r"\s+", " ", name.strip())
    return _SKILL_INDEX.get(_key(cleaned), cleaned)


def find_skill(name: str) -> str | None:
    """Навык из каталога или ``None``, если такого нет."""
    return _SKILL_INDEX.get(_key(name))


def suggest_skills(query: str, limit: int = 10) -> list[str]:
    q = _key(query)
    if not q:
        return []
    starts: list[str] = []
    contains: list[str] = []
    for alias, canonical in _SKILL_INDEX.items():
        if canonical in starts or canonical in contains:
            continue
        if alias.startswith(q):
            starts.append(canonical)
        elif q in alias:
            contains.append(canonical)
    return (sorted(starts, key=len) + sorted(contains, key=len))[:limit]
