"""Общие зависимости FastAPI для эндпоинтов."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import csrf_ok
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.jwt import decode_access_token
from app.db.session import get_session
from app.models.user import User, UserRole
from app.services.account import AccountService
from app.services.auth import AuthService
from app.services.mail_client import MailClient, get_mail_client
from app.services.oauth import OAuthService
from app.services.oidc import ProviderRegistry, get_provider_registry
from app.services.tokens import TokenService

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)


def get_auth_service(
    session: SessionDep,
    mail: Annotated[MailClient, Depends(get_mail_client)],
) -> AuthService:
    return AuthService(session, mail)


def get_account_service(
    session: SessionDep,
    mail: Annotated[MailClient, Depends(get_mail_client)],
) -> AccountService:
    return AccountService(session, mail)


def get_oauth_service(
    session: SessionDep,
    registry: Annotated[ProviderRegistry, Depends(get_provider_registry)],
) -> OAuthService:
    return OAuthService(session, registry)


def get_token_service(session: SessionDep) -> TokenService:
    return TokenService(session)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]
OAuthServiceDep = Annotated[OAuthService, Depends(get_oauth_service)]
TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]
ProviderRegistryDep = Annotated[ProviderRegistry, Depends(get_provider_registry)]


def get_token_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict[str, Any]:
    """Access-токен из заголовка ``Authorization`` или из cookie."""
    token = credentials.credentials if credentials else None
    if token is None:
        token = request.cookies.get(settings.access_cookie_name)
        if token and not csrf_ok(request):
            raise ForbiddenError(
                "CSRF-токен отсутствует или неверен", code="csrf_failed"
            )
    if not token:
        raise UnauthorizedError(headers={"WWW-Authenticate": "Bearer"})
    try:
        return decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise UnauthorizedError(
            "Недействительный токен",
            code="invalid_token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc


async def get_current_user(
    session: SessionDep,
    claims: Annotated[dict[str, Any], Depends(get_token_claims)],
) -> User:
    user = await session.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("Пользователь не найден или заблокирован")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    """Зависимость RBAC: пропускает только пользователей с одной из ролей.

    Пример: ``user: Annotated[User, Depends(require_roles(UserRole.EMPLOYER))]``
    """

    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError()
        return user

    return dependency
