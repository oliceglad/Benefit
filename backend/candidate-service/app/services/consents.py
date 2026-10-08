"""Согласия на обработку и публикацию персональных данных."""

import uuid
from datetime import UTC, datetime

from benefit_common.errors import AppError
from fastapi import status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.candidate import Consent
from app.repositories.candidates import ConsentRepository
from app.schemas.consent import ConsentGrant, ConsentStatus, ConsentType

CONSENT_TITLES = {
    ConsentType.PERSONAL_DATA: "Согласие на обработку персональных данных",
    ConsentType.PUBLICATION: "Согласие на публикацию профиля для работодателей",
}


def current_version(consent_type: ConsentType) -> str:
    return {
        ConsentType.PERSONAL_DATA: settings.consent_personal_data_version,
        ConsentType.PUBLICATION: settings.consent_publication_version,
    }[consent_type]


def document_url(consent_type: ConsentType) -> str:
    return {
        ConsentType.PERSONAL_DATA: settings.consent_personal_data_url,
        ConsentType.PUBLICATION: settings.consent_publication_url,
    }[consent_type]


class ConsentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ConsentRepository(session)

    async def statuses(self, user_id: uuid.UUID) -> list[ConsentStatus]:
        active = {c.type: c for c in await self.repository.active(user_id)}
        result = []
        for consent_type in ConsentType:
            consent = active.get(consent_type)
            required = current_version(consent_type)
            result.append(
                ConsentStatus(
                    type=consent_type,
                    title=CONSENT_TITLES[consent_type],
                    document_url=document_url(consent_type),
                    required_version=required,
                    granted=consent is not None and consent.version == required,
                    granted_version=consent.version if consent else None,
                    granted_at=consent.granted_at if consent else None,
                )
            )
        return result

    async def has(self, user_id: uuid.UUID, consent_type: ConsentType) -> bool:
        return any(
            s.granted for s in await self.statuses(user_id) if s.type == consent_type
        )

    async def has_all(self, user_id: uuid.UUID) -> bool:
        return all(s.granted for s in await self.statuses(user_id))

    async def grant(
        self,
        user_id: uuid.UUID,
        data: ConsentGrant,
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        if data.version != current_version(data.type):
            raise AppError(
                "Версия документа устарела, обновите страницу",
                code="consent_version_mismatch",
                status_code=status.HTTP_409_CONFLICT,
            )
        # Предыдущее согласие того же типа закрываем: в журнале остаётся
        # полная история.
        await self._revoke(user_id, data.type)
        self.repository.session.add(
            Consent(
                user_id=user_id,
                type=data.type,
                version=data.version,
                granted_at=datetime.now(UTC),
                ip_address=ip_address,
                user_agent=(user_agent or "")[:255] or None,
            )
        )
        await self.session.flush()

    async def revoke(self, user_id: uuid.UUID, consent_type: ConsentType) -> None:
        await self._revoke(user_id, consent_type)
        await self.session.flush()

    async def _revoke(self, user_id: uuid.UUID, consent_type: ConsentType) -> None:
        await self.session.execute(
            update(Consent)
            .where(
                Consent.user_id == user_id,
                Consent.type == consent_type,
                Consent.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
