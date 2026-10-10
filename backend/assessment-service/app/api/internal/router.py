"""Внутренний API: статус тестирования кандидата для других сервисов и
удаление данных пользователя (от auth-service)."""

import uuid

from benefit_common.internal import verify_internal_token
from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, or_, select

from app.api.deps import AttemptServiceDep, SessionDep
from app.models import Assessment, Attempt, TestAssignment
from app.schemas.assessment import AssessmentStatus

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)


@router.get("/candidates/{user_id}/status", response_model=AssessmentStatus)
async def candidate_status(
    user_id: uuid.UUID, service: AttemptServiceDep
) -> AssessmentStatus:
    return await service.status(user_id)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, session: SessionDep) -> None:
    """Аккаунт удалён: попытки и результаты кандидата, назначенные ему и
    работодателем тесты, а также собственные тесты работодателя (вместе с
    попытками кандидатов по ним). Идемпотентно."""
    owned = select(Assessment.id).where(Assessment.owner_id == user_id)
    # Попытки ссылаются на тесты и назначения — удаляются первыми.
    await session.execute(
        delete(Attempt).where(
            or_(Attempt.user_id == user_id, Attempt.assessment_id.in_(owned))
        )
    )
    await session.execute(
        delete(TestAssignment).where(
            or_(
                TestAssignment.candidate_id == user_id,
                TestAssignment.employer_id == user_id,
                TestAssignment.assessment_id.in_(owned),
            )
        )
    )
    await session.execute(delete(Assessment).where(Assessment.owner_id == user_id))
    await session.commit()
