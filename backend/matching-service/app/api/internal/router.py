"""Внутренний API: подборка по потребности (вызывает employer-service) и
удаление кандидата из индекса (от auth-service)."""

import uuid

from benefit_common.internal import verify_internal_token
from fastapi import APIRouter, Depends, status
from sqlalchemy import delete

from app.api.deps import SessionDep, TalentServiceDep
from app.models import CandidateIndex
from app.schemas.talent import MatchCriteria, MatchResult

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)


@router.post("/match", response_model=MatchResult)
async def match(criteria: MatchCriteria, service: TalentServiceDep) -> MatchResult:
    return await service.match(criteria)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, session: SessionDep) -> None:
    """Аккаунт удалён: кандидат сразу пропадает из поиска, не дожидаясь
    события об удалении профиля из candidate-service. Идемпотентно."""
    await session.execute(
        delete(CandidateIndex).where(CandidateIndex.user_id == user_id)
    )
    await session.commit()
