"""Вход через внешних OIDC-провайдеров и сопоставление с локальными аккаунтами."""

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, ConflictError, ForbiddenError
from app.core.security import generate_token, hash_token
from app.models.external_identity import ExternalIdentity
from app.models.tokens import OAuthLoginCode, OAuthState
from app.models.user import User, UserRole
from app.repositories.users import ExternalIdentityRepository, UserRepository
from app.schemas.auth import TokenResponse
from app.services.oidc import OIDCProvider, ProviderRegistry
from app.services.tokens import TokenService

logger = logging.getLogger(__name__)


def redirect_uri_for(provider_id: str) -> str:
    base = f"{settings.public_url}{settings.api_v1_prefix}"
    return f"{base}/auth/oauth/{provider_id}/callback"


def role_from_claims(claims: dict[str, Any]) -> UserRole | None:
    """Роль из realm-ролей Keycloak (claim ``realm_access.roles``)."""
    roles = (claims.get("realm_access") or {}).get("roles") or []
    for role in UserRole:
        if role.value in roles:
            return role
    return None


def _full_name(claims: dict[str, Any]) -> str | None:
    if claims.get("name"):
        return claims["name"]
    parts = [claims.get(k) for k in ("family_name", "given_name", "middle_name")]
    return " ".join(p for p in parts if p) or None


@dataclass(frozen=True)
class OAuthResult:
    """Итог возврата от провайдера: код входа или факт привязки аккаунта."""

    login_code: str | None = None
    linked: bool = False


class OAuthService:
    def __init__(self, session: AsyncSession, registry: ProviderRegistry) -> None:
        self.session = session
        self.registry = registry
        self.users = UserRepository(session)
        self.identities = ExternalIdentityRepository(session)
        self.tokens = TokenService(session)

    async def start(
        self,
        provider_id: str,
        role: UserRole | None = None,
        link_user_id: uuid.UUID | None = None,
    ) -> str:
        """Сохраняет state + PKCE и возвращает URL страницы входа провайдера.

        Если передан ``link_user_id``, после возврата внешний аккаунт
        привязывается к этому пользователю вместо входа.
        """
        provider = self.registry.get(provider_id)
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)

        url = await provider.authorization_url(
            redirect_uri=redirect_uri_for(provider.id),
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
        )
        now = datetime.now(UTC)
        # Заодно чистим брошенные попытки входа.
        await self.session.execute(
            delete(OAuthState).where(OAuthState.expires_at < now)
        )
        self.session.add(
            OAuthState(
                state=state,
                provider=provider.id,
                code_verifier=code_verifier,
                nonce=nonce,
                role=role,
                link_user_id=link_user_id,
                expires_at=now + timedelta(minutes=settings.oauth_state_ttl_minutes),
            )
        )
        await self.session.commit()
        return url

    async def complete(self, provider_id: str, code: str, state: str) -> OAuthResult:
        """Обрабатывает возврат от провайдера: вход или привязка аккаунта."""
        provider = self.registry.get(provider_id)
        stored = await self.session.get(OAuthState, state)
        if stored is None or stored.provider != provider.id:
            raise AppError("Сессия входа не найдена", code="invalid_state")
        await self.session.delete(stored)
        await self.session.commit()
        if stored.expires_at <= datetime.now(UTC):
            raise AppError("Сессия входа истекла", code="invalid_state")

        token_response = await provider.exchange_code(
            code=code,
            redirect_uri=redirect_uri_for(provider.id),
            code_verifier=stored.code_verifier,
        )
        id_token = token_response.get("id_token")
        if not id_token:
            raise AppError("Провайдер не вернул ID-токен", code="provider_error")
        claims = await provider.verify_id_token(id_token, nonce=stored.nonce)

        if stored.link_user_id is not None:
            await self._link(provider, claims, stored.link_user_id)
            await self.session.commit()
            return OAuthResult(linked=True)

        user = await self._resolve_user(provider, claims, stored.role)
        if not user.is_active:
            raise ForbiddenError("Аккаунт заблокирован", code="account_disabled")

        login_code = generate_token()
        self.session.add(
            OAuthLoginCode(
                user_id=user.id,
                code_hash=hash_token(login_code),
                expires_at=datetime.now(UTC)
                + timedelta(seconds=settings.oauth_login_code_ttl_seconds),
            )
        )
        await self.session.commit()
        return OAuthResult(login_code=login_code)

    async def exchange(self, login_code: str) -> TokenResponse:
        stored = await self.session.scalar(
            select(OAuthLoginCode)
            .where(OAuthLoginCode.code_hash == hash_token(login_code))
            .with_for_update()
        )
        if stored is None or stored.expires_at <= datetime.now(UTC):
            raise AppError("Код входа недействителен", code="invalid_login_code")
        user = await self.session.get(User, stored.user_id)
        await self.session.delete(stored)
        if user is None or not user.is_active:
            await self.session.commit()
            raise AppError("Код входа недействителен", code="invalid_login_code")

        tokens = await self.tokens.issue(user)
        await self.session.commit()
        return tokens

    async def _link(
        self, provider: OIDCProvider, claims: dict[str, Any], user_id: uuid.UUID
    ) -> None:
        subject = str(claims["sub"])
        identity = await self.identities.get_by_subject(provider.id, subject)
        if identity is not None:
            if identity.user_id != user_id:
                raise ConflictError(
                    "Этот аккаунт уже привязан к другому пользователю",
                    code="identity_taken",
                )
            return
        if await self.identities.get_for_user(user_id, provider.id) is not None:
            raise ConflictError(
                "К профилю уже привязан другой аккаунт этого провайдера",
                code="provider_already_linked",
            )
        self.session.add(
            ExternalIdentity(
                user_id=user_id,
                provider=provider.id,
                subject=subject,
                email=(claims.get("email") or "").lower() or None,
            )
        )
        await self.session.flush()
        logger.info("Linked %s identity to user %s", provider.id, user_id)

    async def _resolve_user(
        self,
        provider: OIDCProvider,
        claims: dict[str, Any],
        requested_role: UserRole | None,
    ) -> User:
        """Находит пользователя по внешнему аккаунту, привязывает существующий
        аккаунт по подтверждённой почте или создаёт новый."""
        subject = str(claims["sub"])
        identity = await self.identities.get_by_subject(provider.id, subject)
        if identity is not None:
            user = await self.session.get(User, identity.user_id)
            assert user is not None
            return user

        email = (claims.get("email") or "").strip().lower()
        if not email:
            raise AppError("Провайдер не передал адрес почты", code="email_required")
        email_verified = bool(claims.get("email_verified"))

        user = await self.users.get_by_email(email)
        if user is not None:
            # Привязка только при подтверждённой провайдером почте — иначе
            # можно захватить чужой аккаунт, указав его почту у провайдера.
            if not email_verified:
                raise ConflictError(
                    "Аккаунт с такой почтой уже существует",
                    code="email_conflict",
                )
            if not user.is_email_verified:
                user.email_verified_at = datetime.now(UTC)
        else:
            role = role_from_claims(claims) or requested_role
            if role is None:
                raise AppError(
                    "Выберите роль: кандидат или работодатель",
                    code="role_required",
                )
            user = User(
                email=email,
                role=role,
                full_name=_full_name(claims),
                email_verified_at=datetime.now(UTC) if email_verified else None,
            )
            self.session.add(user)
            await self.session.flush()
            logger.info("Created user %s via %s", user.id, provider.id)

        self.session.add(
            ExternalIdentity(
                user_id=user.id, provider=provider.id, subject=subject, email=email
            )
        )
        await self.session.flush()
        return user
