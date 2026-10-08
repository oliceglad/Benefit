"""Внутренний API: подборка по потребности (вызывает employer-service)."""

from benefit_common.internal import verify_internal_token
from fastapi import APIRouter, Depends

from app.api.deps import TalentServiceDep
from app.schemas.talent import MatchCriteria, MatchResult

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)


@router.post("/match", response_model=MatchResult)
async def match(criteria: MatchCriteria, service: TalentServiceDep) -> MatchResult:
    return await service.match(criteria)
