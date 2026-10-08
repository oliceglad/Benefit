"""Общие зависимости FastAPI для эндпоинтов."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, Role, TokenError, verify_access_token
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

_bearer = HTTPBearer(auto_error=False)


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return await verify_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_roles(*roles: Role) -> Callable[[Principal], Awaitable[Principal]]:
    """Зависимость RBAC: пропускает только пользователей с одной из ролей."""

    async def dependency(principal: CurrentPrincipal) -> Principal:
        if not principal.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав"
            )
        return principal

    return dependency


Candidate = Annotated[Principal, Depends(require_roles(Role.CANDIDATE))]
Employer = Annotated[Principal, Depends(require_roles(Role.EMPLOYER))]


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
