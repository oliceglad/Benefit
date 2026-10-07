"""Общие зависимости FastAPI для эндпоинтов."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, Role, TokenError, verify_access_token
from app.db.session import get_session

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
    """Зависимость RBAC.

    Пример::

        @router.post("/vacancies")
        async def create_vacancy(
            user: Annotated[Principal, Depends(require_roles(Role.EMPLOYER))],
        ): ...
    """

    async def dependency(principal: CurrentPrincipal) -> Principal:
        if not principal.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав"
            )
        return principal

    return dependency
