"""Экспорт резюме в PDF (HTML-шаблон + WeasyPrint)."""

import base64
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.domain.dictionaries import (
    EDUCATION_LEVEL_TITLES,
    EMPLOYMENT_TYPE_TITLES,
    GRADE_TITLES,
    INDUSTRY_TITLES,
    LANGUAGE_LEVEL_TITLES,
    LINK_TYPE_TITLES,
    ROLE_TITLES,
    SKILL_LEVEL_TITLES,
    WORK_FORMAT_TITLES,
)
from app.schemas.profile import (
    FspAchievementResponse,
    ProfileResponse,
    PublicProfileResponse,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)

MONTHS = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

FSP_RESULTS = {"winner": "Победитель", "prize": "Призёр", "participant": "Участник"}
FSP_LEVELS = {
    "international": "международный уровень",
    "federal": "всероссийский уровень",
    "regional": "региональный уровень",
    "local": "муниципальный уровень",
}


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def format_duration(months: int) -> str:
    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} {plural(years, 'год', 'года', 'лет')}")
    if rest:
        parts.append(f"{rest} {plural(rest, 'месяц', 'месяца', 'месяцев')}")
    return " ".join(parts)


def _month(value: date) -> str:
    return f"{MONTHS[value.month - 1]} {value.year}"


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month + 1


def _salary(amount: int | None, currency: str | None) -> str | None:
    if not amount:
        return None
    symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(currency or "RUB", currency)
    return f"от {amount:,} {symbol}".replace(",", " ")


def _achievement(a: FspAchievementResponse) -> dict[str, str]:
    result = FSP_RESULTS.get(a.result or "", a.result or "")
    if a.place:
        result = f"{result}, {a.place} место" if result else f"{a.place} место"
    details = [a.discipline, result, FSP_LEVELS.get(a.level or "", a.level)]
    if a.team:
        details.append(f"команда «{a.team}»")
    return {
        "date": a.event_date.strftime("%m.%Y") if a.event_date else "",
        "event": a.event,
        "details": " · ".join(d for d in details if d),
    }


def build_context(
    profile: ProfileResponse | PublicProfileResponse,
    photo: bytes | None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    full_name = " ".join(
        p for p in (profile.last_name, profile.first_name, profile.middle_name) if p
    )

    meta = []
    if profile.age is not None:
        meta.append(f"{profile.age} {plural(profile.age, 'год', 'года', 'лет')}")
    if profile.city:
        meta.append(profile.city)
    if profile.relocation_ready:
        meta.append("готов к переезду")
    if profile.roles:
        meta.append(", ".join(ROLE_TITLES[r] for r in profile.roles))
    if profile.industry:
        meta.append(INDUSTRY_TITLES[profile.industry])

    contacts = [
        c for c in (profile.phone, profile.contact_email, profile.telegram) if c
    ]
    contacts += [f"{LINK_TYPE_TITLES[link.type]}: {link.url}" for link in profile.links]

    preferences = []
    if profile.headline:
        preferences.append(profile.headline)
    salary = _salary(profile.salary_from, profile.salary_currency)
    if salary:
        preferences.append(salary)
    if profile.employment_types:
        preferences.append(
            "Занятость: "
            + ", ".join(EMPLOYMENT_TYPE_TITLES[t] for t in profile.employment_types)
        )
    if profile.work_formats:
        preferences.append(
            "Формат работы: "
            + ", ".join(WORK_FORMAT_TITLES[f] for f in profile.work_formats)
        )

    skills = [
        f"{s.name} ({SKILL_LEVEL_TITLES[s.level].lower()})" if s.level else s.name
        for s in profile.skills
    ]

    experience = []
    for job in profile.experience:
        end = job.end_date or today
        experience.append(
            {
                "period": f"{_month(job.start_date)} — "
                + (_month(job.end_date) if job.end_date else "настоящее время"),
                "duration": format_duration(_months_between(job.start_date, end)),
                "company": job.company,
                "city": job.city,
                "position": job.position,
                "description": job.description,
                "achievements": job.achievements,
                "technologies": job.technologies,
            }
        )

    education = [
        {
            "institution": e.institution,
            "graduation_year": e.graduation_year,
            "details": ", ".join(
                d
                for d in (
                    EDUCATION_LEVEL_TITLES[e.level] if e.level else None,
                    e.faculty,
                    e.specialization,
                )
                if d
            ),
        }
        for e in profile.education
    ]

    achievements = (
        profile.fsp.achievements
        if isinstance(profile, ProfileResponse)
        else profile.fsp_achievements
    )

    photo_uri = (
        "data:image/jpeg;base64," + base64.b64encode(photo).decode() if photo else None
    )
    return {
        "full_name": full_name,
        "headline": profile.headline,
        "grade": (
            GRADE_TITLES[profile.category.grade] if profile.category.grade else None
        ),
        "grade_confirmed": profile.category.grade_status == "confirmed",
        "meta": meta,
        "contacts": contacts,
        "preferences": preferences,
        "about": profile.about,
        "skills": skills,
        "total_experience": format_duration(profile.total_experience_months),
        "experience": experience,
        "projects": profile.projects,
        "fsp_achievements": [_achievement(a) for a in achievements],
        "education": education,
        "courses": profile.courses,
        "languages": [
            f"{lang.language} — {LANGUAGE_LEVEL_TITLES[lang.level]}"
            for lang in profile.languages
        ],
        "soft_skills": profile.soft_skills,
        "photo_data_uri": photo_uri,
        "generated_at": today.strftime("%d.%m.%Y"),
    }


def render_resume_pdf(context: dict[str, Any]) -> bytes:
    """CPU-ёмкая операция: вызывать из пула потоков."""
    # Тяжёлый импорт: только при генерации.
    from weasyprint import HTML
    from weasyprint.urls import URLFetcher

    html = _env.get_template("resume.html").render(**context)
    # Встраивается только фото (data:) — без сетевых запросов и чтения
    # локальных файлов, даже если в шаблон попадёт чужой URL.
    fetcher = URLFetcher(allowed_protocols={"data"})
    return HTML(
        string=html, base_url=str(TEMPLATES_DIR), url_fetcher=fetcher
    ).write_pdf()
