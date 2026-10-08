"""Репозитории пользователей и внешних аккаунтов."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.external_identity import ExternalIdentity
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(
            select(User).where(User.email == email.lower())
        )


class ExternalIdentityRepository(BaseRepository[ExternalIdentity]):
    model = ExternalIdentity

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[ExternalIdentity]:
        result = await self.session.scalars(
            select(ExternalIdentity)
            .where(ExternalIdentity.user_id == user_id)
            .order_by(ExternalIdentity.created_at)
        )
        return result.all()

    async def get_for_user(
        self, user_id: uuid.UUID, provider: str
    ) -> ExternalIdentity | None:
        return await self.session.scalar(
            select(ExternalIdentity).where(
                ExternalIdentity.user_id == user_id,
                ExternalIdentity.provider == provider,
            )
        )

    async def get_by_subject(
        self, provider: str, subject: str
    ) -> ExternalIdentity | None:
        return await self.session.scalar(
            select(ExternalIdentity).where(
                ExternalIdentity.provider == provider,
                ExternalIdentity.subject == subject,
            )
        )
