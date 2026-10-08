"""Справочники для форм профиля."""

from enum import StrEnum
from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.domain import dictionaries as d

router = APIRouter(prefix="/dictionaries", tags=["candidate: справочники"])


def _options(titles: dict[Any, str]) -> list[dict[str, str]]:
    return [
        {"id": key.value if isinstance(key, StrEnum) else key, "title": title}
        for key, title in titles.items()
    ]


@router.get("")
async def get_dictionaries() -> dict[str, Any]:
    return {
        "grades": _options(d.GRADE_TITLES),
        "roles": _options(d.ROLE_TITLES),
        "skill_levels": _options(d.SKILL_LEVEL_TITLES),
        "language_levels": _options(d.LANGUAGE_LEVEL_TITLES),
        "languages": d.LANGUAGES,
        "employment_types": _options(d.EMPLOYMENT_TYPE_TITLES),
        "work_formats": _options(d.WORK_FORMAT_TITLES),
        "job_search_statuses": _options(d.JOB_SEARCH_STATUS_TITLES),
        "education_levels": _options(d.EDUCATION_LEVEL_TITLES),
        "link_types": _options(d.LINK_TYPE_TITLES),
        "soft_skills": d.SOFT_SKILLS,
    }


@router.get("/skills", response_model=list[str])
async def suggest_skills(
    q: Annotated[str, Query(min_length=1, max_length=64)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[str]:
    """Подсказки навыков: учитывает синонимы («питон» → Python)."""
    return d.suggest_skills(q, limit)
