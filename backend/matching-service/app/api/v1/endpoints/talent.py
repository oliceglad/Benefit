"""Поиск по банку кандидатов — для работодателей.

Доступна вся база опубликованных профилей с фильтрами по специализации,
грейду, категории (подтверждён ли грейд), стеку и наличию достижений ФСП.
Контактов в выдаче нет: они открываются после принятия приглашения
или отклика кандидата.
"""

import uuid
from typing import Annotated, Literal

from benefit_common.dictionaries import Grade, Industry, ITRole, WorkFormat
from benefit_common.security import Employer
from benefit_common.skills import normalize_skill
from fastapi import APIRouter, Query

from app.api.deps import TalentServiceDep
from app.schemas.talent import SearchPage, SimilarCandidate

router = APIRouter(tags=["talent: банк кандидатов"])


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/candidates", response_model=SearchPage)
async def search_candidates(
    _: Employer,
    service: TalentServiceDep,
    specialization: ITRole | None = None,
    grade: Annotated[list[Grade] | None, Query()] = None,
    grade_status: Literal["confirmed", "not_confirmed"] | None = None,
    skills: Annotated[list[str] | None, Query(description="Навыки")] = None,
    skills_mode: Annotated[
        Literal["all", "any"], Query(description="all — все навыки, any — любой")
    ] = "all",
    has_fsp: Annotated[
        bool | None, Query(description="Есть подтверждённые достижения ФСП")
    ] = None,
    industry: Industry | None = None,
    city: Annotated[str | None, Query(max_length=100)] = None,
    work_format: WorkFormat | None = None,
    q: Annotated[
        str | None, Query(max_length=200, description="Полнотекстовый поиск")
    ] = None,
    experience_min: Annotated[
        float | None, Query(ge=0, le=50, description="Лет")
    ] = None,
    experience_max: Annotated[
        float | None, Query(ge=0, le=50, description="Лет")
    ] = None,
    salary_max: Annotated[
        int | None, Query(ge=0, description="Бюджет: ожидания не выше")
    ] = None,
    active_only: Annotated[
        bool, Query(description="Только с активностью за 30 дней")
    ] = False,
    include_not_looking: bool = False,
    sort: Literal[
        "relevance", "skills", "actuality", "experience", "fsp"
    ] = "relevance",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchPage:
    """Поиск с фасетами по категориям (специализация + грейд + подтверждение)."""
    return await service.search(
        specialization=specialization,
        grades=list(grade or []),
        grade_status=grade_status,
        skills=[normalize_skill(s) for s in skills or []],
        skills_mode=skills_mode,
        has_fsp=has_fsp,
        industry=industry,
        city=city,
        work_format=work_format,
        q=q,
        experience_min_months=round(experience_min * 12) if experience_min else None,
        experience_max_months=round(experience_max * 12) if experience_max else None,
        salary_max=salary_max,
        active_only=active_only,
        include_not_looking=include_not_looking,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get("/candidates/{user_id}/similar", response_model=list[SimilarCandidate])
async def similar_candidates(
    user_id: uuid.UUID,
    _: Employer,
    service: TalentServiceDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[SimilarCandidate]:
    """Похожие кандидаты: общий стек, специализация, близкий грейд."""
    return await service.similar(user_id, limit)
