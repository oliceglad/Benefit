"""Репозитории пользователей и внешних аккаунтов."""

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

    async def get_by_subject(
        self, provider: str, subject: str
    ) -> ExternalIdentity | None:
        return await self.session.scalar(
            select(ExternalIdentity).where(
                ExternalIdentity.provider == provider,
                ExternalIdentity.subject == subject,
            )
        )
