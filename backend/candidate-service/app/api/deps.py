"""Общие зависимости FastAPI для эндпоинтов."""

from typing import Annotated

from benefit_common.security import Candidate, Employer, Principal
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.candidate import CandidateProfile
from app.services.fsp import (
    AchievementsClient,
    FspSyncService,
    IdentityClient,
    get_achievements_client,
    get_identity_client,
)
from app.services.pdf_import import ResumeParser, get_resume_parser
from app.services.profiles import ProfileService

SessionDep = Annotated[AsyncSession, Depends(get_session)]

__all__ = ["Candidate", "Employer", "Principal"]


def get_profile_service(session: SessionDep) -> ProfileService:
    return ProfileService(session)


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


async def get_my_profile(
    principal: Candidate, service: ProfileServiceDep
) -> CandidateProfile:
    """Профиль текущего кандидата; создаётся при первом обращении.

    Все эндпоинты ``/me`` работают только с профилем владельца токена:
    идентификатор берётся из токена, а не из запроса.
    """
    return await service.get_or_create(principal)


MyProfile = Annotated[CandidateProfile, Depends(get_my_profile)]


def get_fsp_sync_service(
    session: SessionDep,
    identities: Annotated[IdentityClient, Depends(get_identity_client)],
    achievements: Annotated[AchievementsClient, Depends(get_achievements_client)],
) -> FspSyncService:
    return FspSyncService(session, identities, achievements)


FspSyncServiceDep = Annotated[FspSyncService, Depends(get_fsp_sync_service)]
ResumeParserDep = Annotated[ResumeParser, Depends(get_resume_parser)]
