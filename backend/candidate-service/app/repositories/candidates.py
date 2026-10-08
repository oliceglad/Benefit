"""Репозитории candidate-service."""

import uuid
from collections.abc import Sequence

from sqlalchemy import exists, select

from app.models.candidate import (
    CandidatePhoto,
    CandidateProfile,
    Consent,
    FspAchievement,
)
from app.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[CandidateProfile]):
    model = CandidateProfile

    async def has_photo(self, user_id: uuid.UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(exists().where(CandidatePhoto.user_id == user_id))
            )
        )

    async def achievements(self, user_id: uuid.UUID) -> Sequence[FspAchievement]:
        result = await self.session.scalars(
            select(FspAchievement)
            .where(FspAchievement.user_id == user_id)
            .order_by(FspAchievement.event_date.desc().nulls_last())
        )
        return result.all()


class ConsentRepository(BaseRepository[Consent]):
    model = Consent

    async def active(self, user_id: uuid.UUID) -> Sequence[Consent]:
        result = await self.session.scalars(
            select(Consent).where(
                Consent.user_id == user_id, Consent.revoked_at.is_(None)
            )
        )
        return result.all()
