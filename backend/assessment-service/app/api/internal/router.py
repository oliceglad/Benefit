"""Внутренний API: статус тестирования кандидата для других сервисов
(например, будущего сервиса подбора вакансий)."""

import uuid

from benefit_common.internal import verify_internal_token
from fastapi import APIRouter, Depends

from app.api.deps import AttemptServiceDep
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
