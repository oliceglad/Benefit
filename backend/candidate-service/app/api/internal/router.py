"""Внутренний API для других сервисов Benefit.

Точки интеграции для будущих сервисов:
* подбор вакансий (matching-service) — снимки профилей и лента событий;
* тестирование по грейду (assessment-service) — запись подтверждённого грейда;
* тесты на навыки (assessment-service) — подтверждённые уровни навыков.

Через шлюз не публикуется; защищён межсервисным токеном.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from benefit_common.internal import verify_internal_token
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api.deps import ProfileServiceDep, SessionDep
from app.domain.dictionaries import Grade, Industry, ITRole
from app.models.candidate import (
    CandidateActivity,
    CandidateProfile,
    ContactGrant,
    OutboxEvent,
    ProfileStatus,
)
from app.schemas.profile import PublicProfileResponse
from app.services.events import EventType, record_event
from app.services.profiles import matching_snapshot

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)


class CandidateSnapshot(BaseModel):
    user_id: uuid.UUID
    updated_at: datetime
    data: dict[str, Any]


class AssessmentResult(BaseModel):
    """Итог тестирования от assessment-service.

    ``verified_grade`` — лучший действующий подтверждённый грейд кандидата
    (``None``, если подтверждённых результатов нет). Низкий результат сюда
    не передаётся: assessment-service присылает только подтверждения.
    """

    industry: Industry | None = None
    specialization: ITRole | None = None
    verified_grade: Grade | None = None
    verified_at: datetime | None = None
    attempt_id: uuid.UUID | None = None
    test_title: str | None = None
    percent: float | None = None


class SkillVerificationLevel(BaseModel):
    id: str = Field(max_length=16)
    title: str = Field(max_length=100)
    min_percent: float | None = None


class SkillVerification(BaseModel):
    level: SkillVerificationLevel
    verified_at: datetime
    valid_until: datetime
    attempt_id: uuid.UUID
    percent: float
    test_title: str = Field(max_length=200)


class SkillVerificationRequest(BaseModel):
    """Лучший действующий уровень навыка; ``None`` — подтверждения нет."""

    skill: str = Field(min_length=1, max_length=64)
    verification: SkillVerification | None = None


class ContactGrantRequest(BaseModel):
    employer_id: uuid.UUID
    source: Literal["invitation", "application"]
    source_id: uuid.UUID


class ActivityRequest(BaseModel):
    kind: Literal[
        "task_assigned",
        "task_submitted",
        "task_reviewed",
        "task_expired",
        "employer_test_completed",
        "employer_test_expired",
    ]
    ref_id: str = Field(max_length=64)
    occurred_at: datetime
    data: dict[str, Any] = Field(default_factory=dict)


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


@router.get(
    "/candidates/{user_id}/search-document", response_model=PublicProfileResponse
)
async def search_document(
    user_id: uuid.UUID, service: ProfileServiceDep
) -> PublicProfileResponse:
    """Данные для поискового индекса (matching-service).

    Это профиль глазами работодателя без доступа к контактам: настройки
    приватности применены, контактов нет. Неопубликованный профиль — 404
    (его нужно убрать из индекса).
    """
    return await service.public_view(user_id, None)


@router.get("/candidates/{user_id}", response_model=CandidateSnapshot)
async def get_candidate(
    user_id: uuid.UUID, service: ProfileServiceDep
) -> CandidateSnapshot:
    return _snapshot(await service.get(user_id))


@router.put("/candidates/{user_id}/assessment", response_model=CandidateSnapshot)
async def set_assessment_result(
    user_id: uuid.UUID,
    data: AssessmentResult,
    service: ProfileServiceDep,
    session: SessionDep,
) -> CandidateSnapshot:
    """Обновляет категорию кандидата по итогам тестирования.

    Идемпотентно: повторная доставка того же результата ничего не меняет.
    """
    profile = await service.get(user_id)
    if data.industry:
        profile.industry = data.industry
    profile.verified_grade = data.verified_grade
    profile.verified_specialization = (
        data.specialization if data.verified_grade else None
    )
    profile.grade_verified_at = data.verified_at if data.verified_grade else None
    profile.verification = (
        {
            "attempt_id": str(data.attempt_id) if data.attempt_id else None,
            "test_title": data.test_title,
            "percent": data.percent,
        }
        if data.verified_grade
        else {}
    )
    record_event(
        session,
        user_id,
        EventType.GRADE_VERIFIED,
        {
            "verified_grade": data.verified_grade,
            "specialization": data.specialization,
            "industry": profile.industry,
            "attempt_id": str(data.attempt_id) if data.attempt_id else None,
        },
    )
    await session.commit()
    await session.refresh(profile)
    return _snapshot(profile)


@router.put(
    "/candidates/{user_id}/skill-verifications", response_model=CandidateSnapshot
)
async def set_skill_verification(
    user_id: uuid.UUID,
    data: SkillVerificationRequest,
    service: ProfileServiceDep,
    session: SessionDep,
) -> CandidateSnapshot:
    """Подтверждённый тестом уровень навыка (английский, SQL, Git…).

    Идемпотентно: запись по навыку заменяется целиком.
    """
    profile = await service.get(user_id)
    others = [
        item
        for item in profile.verified_skills or []
        if item["skill"].lower() != data.skill.lower()
    ]
    if data.verification is not None:
        others.append(
            {
                "skill": data.skill,
                **data.verification.model_dump(mode="json", exclude={"level"}),
                "level": data.verification.level.model_dump(
                    mode="json", include={"id", "title"}
                ),
            }
        )
    profile.verified_skills = sorted(others, key=lambda item: item["skill"].lower())
    record_event(
        session,
        user_id,
        EventType.SKILL_VERIFIED,
        {
            "skill": data.skill,
            "level": data.verification.level.id if data.verification else None,
        },
    )
    await session.commit()
    await session.refresh(profile)
    return _snapshot(profile)


@router.put(
    "/candidates/{user_id}/contact-grants",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def grant_contacts(
    user_id: uuid.UUID,
    data: ContactGrantRequest,
    service: ProfileServiceDep,
    session: SessionDep,
) -> None:
    """Открывает работодателю контакты кандидата: кандидат принял его
    приглашение или откликнулся на вакансию. Идемпотентно."""
    await service.get(user_id)
    await session.execute(
        pg_insert(ContactGrant)
        .values(
            id=uuid.uuid4(),
            candidate_id=user_id,
            employer_id=data.employer_id,
            source=data.source,
            source_id=data.source_id,
        )
        .on_conflict_do_update(
            index_elements=["candidate_id", "employer_id"],
            set_={"source": data.source, "source_id": data.source_id},
        )
    )
    record_event(
        session,
        user_id,
        EventType.CONTACTS_SHARED,
        {
            "employer_id": str(data.employer_id),
            "source": data.source,
            "source_id": str(data.source_id),
        },
    )
    await session.commit()


@router.put("/candidates/{user_id}/activities", status_code=status.HTTP_204_NO_CONTENT)
async def record_activity(
    user_id: uuid.UUID,
    data: ActivityRequest,
    service: ProfileServiceDep,
    session: SessionDep,
) -> None:
    """Активность по заданиям работодателей (из chat-service). Влияет на
    актуальность профиля. Идемпотентно по (kind, ref_id)."""
    await service.get(user_id)
    result = await session.execute(
        pg_insert(CandidateActivity)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            kind=data.kind,
            ref_id=data.ref_id,
            occurred_at=data.occurred_at,
            data=data.data,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "kind", "ref_id"])
    )
    if result.rowcount:
        record_event(
            session,
            user_id,
            EventType.ACTIVITY_RECORDED,
            {"kind": data.kind, "ref_id": data.ref_id, "data": data.data},
        )
    await session.commit()


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


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID, service: ProfileServiceDep, session: SessionDep
) -> None:
    """Аккаунт удалён в auth-service: удаляем профиль кандидата (с фото,
    достижениями и открытыми контактами) и доступы удалённого работодателя
    к контактам кандидатов. Идемпотентно.

    Журнал согласий сохраняется с отметкой об отзыве — как подтверждение
    законности обработки данных в прошлом.
    """
    profile = await service.profiles.get(user_id)
    if profile is not None:
        # Событие удаления профиля уберёт кандидата из поиска (matching).
        await service.delete(profile)
    await session.execute(
        delete(ContactGrant).where(ContactGrant.employer_id == user_id)
    )
    await session.commit()
