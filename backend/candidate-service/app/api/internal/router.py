"""Внутренний API для других сервисов Benefit.

Точки интеграции для будущих сервисов:
* подбор вакансий (matching-service) — снимки профилей и лента событий;
* тестирование по грейду (assessment-service) — запись подтверждённого грейда.

Через шлюз не публикуется; защищён межсервисным токеном.
"""

import hmac
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import ProfileServiceDep, SessionDep
from app.core.config import settings
from app.domain.dictionaries import Grade
from app.models.candidate import CandidateProfile, OutboxEvent, ProfileStatus
from app.services.events import EventType, record_event
from app.services.profiles import matching_snapshot


def verify_internal_token(x_internal_token: Annotated[str, Header()] = "") -> None:
    if not hmac.compare_digest(x_internal_token, settings.internal_api_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)


class CandidateSnapshot(BaseModel):
    user_id: uuid.UUID
    updated_at: datetime
    data: dict[str, Any]


class VerifiedGradeRequest(BaseModel):
    grade: Grade
    # Идентификатор попытки тестирования в assessment-service.
    assessment_id: str | None = None


class EventResponse(BaseModel):
    id: int
    aggregate_id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


def _snapshot(profile: CandidateProfile) -> CandidateSnapshot:
    return CandidateSnapshot(
        user_id=profile.user_id,
        updated_at=profile.updated_at,
        data=matching_snapshot(profile),
    )


@router.get("/candidates", response_model=list[CandidateSnapshot])
async def list_candidates(
    session: SessionDep,
    only_published: bool = True,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CandidateSnapshot]:
    """Пакетная выгрузка для первичной индексации в сервисе подбора."""
    query = select(CandidateProfile).order_by(CandidateProfile.user_id)
    if only_published:
        query = query.where(CandidateProfile.status == ProfileStatus.PUBLISHED)
    profiles = await session.scalars(query.limit(limit).offset(offset))
    return [_snapshot(p) for p in profiles]


@router.get("/candidates/{user_id}", response_model=CandidateSnapshot)
async def get_candidate(
    user_id: uuid.UUID, service: ProfileServiceDep
) -> CandidateSnapshot:
    return _snapshot(await service.get(user_id))


@router.put("/candidates/{user_id}/verified-grade", response_model=CandidateSnapshot)
async def set_verified_grade(
    user_id: uuid.UUID,
    data: VerifiedGradeRequest,
    service: ProfileServiceDep,
    session: SessionDep,
) -> CandidateSnapshot:
    """Грейд, подтверждённый тестированием. Показывается рядом с заявленным."""
    profile = await service.get(user_id)
    profile.verified_grade = data.grade
    profile.grade_verified_at = datetime.now(UTC)
    record_event(
        session,
        user_id,
        EventType.GRADE_VERIFIED,
        {"grade": data.grade, "assessment_id": data.assessment_id},
    )
    await session.commit()
    await session.refresh(profile)
    return _snapshot(profile)


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    session: SessionDep,
    after_id: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[EventResponse]:
    """Лента доменных событий. Потребитель хранит последний ``id`` и
    запрашивает следующие события (at-least-once)."""
    events = await session.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.id > after_id)
        .order_by(OutboxEvent.id)
        .limit(limit)
    )
    return [
        EventResponse(
            id=e.id,
            aggregate_id=e.aggregate_id,
            event_type=e.event_type,
            payload=e.payload,
            created_at=e.created_at,
        )
        for e in events
    ]
