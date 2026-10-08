"""Проверка access-токенов auth-service и RBAC.

Токены подписаны RS256; публичные ключи берутся из JWKS auth-service и
кэшируются. Формат claims совместим с Keycloak (``realm_access.roles``).
"""

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from benefit_common.settings import get_common_settings

JWKS_TTL_SECONDS = 600


class Role(StrEnum):
    CANDIDATE = "candidate"
    EMPLOYER = "employer"
    ADMIN = "admin"


@dataclass(frozen=True)
class Principal:
    """Аутентифицированный пользователь из access-токена."""

    id: uuid.UUID
    email: str
    roles: frozenset[str]
    name: str | None = None

    def has_role(self, *roles: Role) -> bool:
        return any(role.value in self.roles for role in roles)


class TokenError(Exception):
    pass


class JWKSCache:
    def __init__(self, url: str) -> None:
        self.url = url
        self._keys: dict[str, jwt.PyJWK] = {}
        self._loaded_at = 0.0

    async def _load(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.url)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TokenError("JWKS unavailable") from exc
        self._keys = {
            key["kid"]: jwt.PyJWK(key)
            for key in data.get("keys", [])
            if key.get("use", "sig") == "sig" and "kid" in key
        }
        self._loaded_at = time.monotonic()

    async def get(self, kid: str) -> jwt.PyJWK:
        expired = time.monotonic() - self._loaded_at > JWKS_TTL_SECONDS
        if kid not in self._keys or expired:
            # Неизвестный kid — возможно, ключ ротировали: перечитываем JWKS.
            await self._load()
        try:
            return self._keys[kid]
        except KeyError as exc:
            raise TokenError("Unknown signing key") from exc


jwks_cache = JWKSCache(get_common_settings().auth_jwks_url)


async def verify_access_token(token: str) -> Principal:
    settings = get_common_settings()
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        if not kid:
            raise TokenError("Token has no kid")
        key = await jwks_cache.get(kid)
        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.auth_audience,
            issuer=settings.auth_issuer,
            options={"require": ["exp", "sub"]},
        )
        return Principal(
            id=uuid.UUID(claims["sub"]),
            email=claims.get("email", ""),
            roles=frozenset((claims.get("realm_access") or {}).get("roles", [])),
            name=claims.get("name"),
        )
    except (jwt.PyJWTError, ValueError) as exc:
        raise TokenError(str(exc)) from exc


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


Candidate = Annotated[Principal, Depends(require_roles(Role.CANDIDATE))]
Employer = Annotated[Principal, Depends(require_roles(Role.EMPLOYER))]
Admin = Annotated[Principal, Depends(require_roles(Role.ADMIN))]
