"""Репозитории candidate-service."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import exists, func, literal_column, select

from app.models.candidate import (
    CandidateActivity,
    CandidatePhoto,
    CandidateProfile,
    Consent,
    ContactGrant,
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

    async def activity_stats(
        self, user_id: uuid.UUID, since: datetime
    ) -> tuple[dict[str, int], datetime | None]:
        """Счётчики активности по видам (с ``since``) и время последней
        собственной активности кандидата (отправка решения)."""
        # Ключ — литералом: одинаковое выражение в SELECT и GROUP BY.
        result = CandidateActivity.data.op("->>")(literal_column("'result'"))
        rows = await self.session.execute(
            select(CandidateActivity.kind, result, func.count())
            .where(
                CandidateActivity.user_id == user_id,
                CandidateActivity.occurred_at >= since,
            )
            .group_by(CandidateActivity.kind, result)
        )
        counts: dict[str, int] = {}
        for kind, result, count in rows:
            key = f"{kind}:{result}" if result else kind
            counts[key] = counts.get(key, 0) + count
        last = await self.session.scalar(
            select(func.max(CandidateActivity.occurred_at)).where(
                CandidateActivity.user_id == user_id,
                # Собственные действия кандидата.
                CandidateActivity.kind.in_(
                    ["task_submitted", "employer_test_completed"]
                ),
            )
        )
        return counts, last

    async def has_contact_grant(
        self, candidate_id: uuid.UUID, employer_id: uuid.UUID
    ) -> bool:
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        ContactGrant.candidate_id == candidate_id,
                        ContactGrant.employer_id == employer_id,
                    )
                )
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
