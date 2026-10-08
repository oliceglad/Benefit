"""Каталог IT-навыков с синонимами.

Нормализация нужна, чтобы «питон», «python3» и «Python» были одним навыком
во всех сервисах: в профиле кандидата, в потребностях и вакансиях
работодателя, в поиске и подборе.
"""

import re

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


# Близкие технологии: взаимозаменяемы с небольшим переобучением. Используются
# в подборе для частичного зачёта навыка («нет Kafka, но есть RabbitMQ»).
SKILL_FAMILIES: list[set[str]] = [
    {"FastAPI", "Django", "Flask", "aiohttp"},
    {"Spring", ".NET", "NestJS", "Express", "Laravel", "Ruby on Rails"},
    {"PostgreSQL", "MySQL", "MS SQL Server", "Oracle"},
    {"MongoDB", "Cassandra"},
    {"Kafka", "RabbitMQ", "NATS"},
    {"React", "Vue.js", "Angular", "Svelte"},
    {"Next.js", "Nuxt"},
    {"JavaScript", "TypeScript"},
    {"Java", "Kotlin", "Scala"},
    {"C++", "C", "Rust"},
    {"Go", "Rust"},
    {"Swift", "Objective-C"},
    {"Flutter", "React Native"},
    {"Android", "Jetpack Compose"},
    {"iOS", "SwiftUI"},
    {"GitLab CI", "GitHub Actions", "Jenkins", "CI/CD"},
    {"Terraform", "Ansible"},
    {"AWS", "Yandex Cloud"},
    {"Prometheus", "Grafana"},
    {"PyTorch", "TensorFlow", "Keras"},
    {"CatBoost", "XGBoost", "LightGBM"},
    {"Apache Spark", "Hadoop"},
    {"Power BI", "Tableau"},
    {"Selenium", "Playwright", "Cypress"},
    {"Pytest", "JUnit"},
    {"Unity", "Unreal Engine"},
    {"Webpack", "Vite"},
]

_RELATED: dict[str, set[str]] = {}
for _family in SKILL_FAMILIES:
    for _skill in _family:
        _RELATED.setdefault(_skill.lower(), set()).update(
            s for s in _family if s != _skill
        )


def related_skills(name: str) -> set[str]:
    """Близкие технологии к навыку (канонические названия)."""
    return _RELATED.get(normalize_skill(name).lower(), set())
