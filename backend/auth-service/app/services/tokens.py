"""Выпуск и ротация пар access/refresh токенов."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.jwt import create_access_token
from app.core.security import generate_token, hash_token
from app.models.tokens import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenResponse


class TokenService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def issue(self, user: User) -> TokenResponse:
        """Создаёт пару токенов. Коммит — на стороне вызывающего."""
        access_token, expires_in = create_access_token(
            subject=str(user.id),
            roles=[user.role.value],
            email=user.email,
            email_verified=user.is_email_verified,
            name=user.full_name,
        )
        refresh_token = generate_token()
        refresh_ttl = timedelta(days=settings.refresh_token_ttl_days)
        self.session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(refresh_token),
                expires_at=datetime.now(UTC) + refresh_ttl,
            )
        )
        await self.session.flush()
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            refresh_expires_in=int(refresh_ttl.total_seconds()),
        )

    async def rotate(self, refresh_token: str) -> TokenResponse:
        """Обменивает refresh-токен на новую пару; старый отзывается.

        Повторное использование отозванного токена означает его утечку:
        тогда отзываются все сессии пользователя.
        """
        invalid = UnauthorizedError(
            "Refresh-токен недействителен", code="invalid_refresh_token"
        )
        stored = await self.session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_token(refresh_token))
            .with_for_update()
        )
        if stored is None:
            raise invalid

        now = datetime.now(UTC)
        if stored.revoked_at is not None:
            await self.revoke_all(stored.user_id)
            await self.session.commit()
            raise invalid
        if stored.expires_at <= now:
            raise invalid

        user = await self.session.get(User, stored.user_id)
        if user is None or not user.is_active:
            raise invalid

        stored.revoked_at = now
        tokens = await self.issue(user)
        await self.session.commit()
        return tokens

    async def revoke(self, refresh_token: str) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == hash_token(refresh_token),
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        await self.session.commit()

    async def revoke_all(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
