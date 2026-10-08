"""Связь профиля с участником ФСП и синхронизация достижений.

ID участника берётся из auth-service: это ``sub`` привязанного аккаунта
ФСП ID. Достижения загружаются из API ФСП и хранятся как копия только
для чтения: кандидат не может их редактировать.
"""

import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any, Protocol

import httpx
from fastapi import status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.candidate import CandidateProfile, FspAchievement
from app.services.events import EventType, record_event

logger = logging.getLogger(__name__)


class ExternalServiceError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "fsp_unavailable"
    message = "Сервис ФСП временно недоступен"


class IdentityClient(Protocol):
    async def fsp_participant_id(self, user_id: uuid.UUID) -> str | None: ...


class AchievementsClient(Protocol):
    async def achievements(self, participant_id: str) -> list[dict[str, Any]]: ...


class AuthInternalClient:
    async def fsp_participant_id(self, user_id: uuid.UUID) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{settings.auth_internal_url}/internal/v1/users/{user_id}/identities",
                    headers={"X-Internal-Token": settings.internal_api_token},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("auth-service identities request failed")
            raise ExternalServiceError("Не удалось проверить привязку ФСП ID") from exc
        for identity in response.json():
            if identity["provider"] == settings.fsp_provider_id:
                return identity["subject"]
        return None


class FspApiClient:
    async def achievements(self, participant_id: str) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.fsp_api_url}/api/v1/participants/{participant_id}/achievements",
                    auth=(settings.fsp_client_id, settings.fsp_client_secret),
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("FSP achievements request failed")
            raise ExternalServiceError() from exc
        return response.json().get("items", [])


def get_identity_client() -> IdentityClient:
    return AuthInternalClient()


def get_achievements_client() -> AchievementsClient:
    return FspApiClient()


def _to_model(user_id: uuid.UUID, item: dict[str, Any]) -> FspAchievement:
    event_date = item.get("date")
    return FspAchievement(
        user_id=user_id,
        external_id=str(item["id"])[:64],
        event=str(item.get("event") or "Соревнование ФСП")[:300],
        discipline=item.get("discipline"),
        level=item.get("level"),
        result=item.get("result"),
        place=item.get("place"),
        team=item.get("team"),
        event_date=date.fromisoformat(event_date) if event_date else None,
        url=item.get("url"),
    )


class FspSyncService:
    def __init__(
        self,
        session: AsyncSession,
        identities: IdentityClient,
        achievements: AchievementsClient,
    ) -> None:
        self.session = session
        self.identities = identities
        self.achievements = achievements

    async def sync(self, profile: CandidateProfile) -> None:
        """Обновляет связь с ФСП и список достижений."""
        participant_id = await self.identities.fsp_participant_id(profile.user_id)
        items = (
            await self.achievements.achievements(participant_id)
            if participant_id
            else []
        )

        await self.session.execute(
            delete(FspAchievement).where(FspAchievement.user_id == profile.user_id)
        )
        self.session.add_all(_to_model(profile.user_id, item) for item in items)
        profile.fsp_participant_id = participant_id
        profile.fsp_synced_at = datetime.now(UTC) if participant_id else None
        record_event(
            self.session,
            profile.user_id,
            EventType.FSP_ACHIEVEMENTS_SYNCED,
            {"participant_id": participant_id, "count": len(items)},
        )
        await self.session.commit()
        await self.session.refresh(profile)

        if participant_id is None:
            raise AppError(
                "Профиль не связан с ФСП ID. Привяжите аккаунт через "
                "POST /api/v1/auth/oauth/fsp_id/link",
                code="fsp_not_linked",
                status_code=status.HTTP_409_CONFLICT,
            )
