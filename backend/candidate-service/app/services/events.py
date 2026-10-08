"""Доменные события профиля (transactional outbox)."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import OutboxEvent


class EventType:
    PROFILE_PUBLISHED = "candidate.profile.published"
    PROFILE_UPDATED = "candidate.profile.updated"
    PROFILE_UNPUBLISHED = "candidate.profile.unpublished"
    PROFILE_DELETED = "candidate.profile.deleted"
    GRADE_VERIFIED = "candidate.grade.verified"
    FSP_ACHIEVEMENTS_SYNCED = "candidate.fsp_achievements.synced"


def record_event(
    session: AsyncSession,
    aggregate_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Добавляет событие в текущую транзакцию: оно сохранится только
    вместе с изменением, которое его породило."""
    session.add(
        OutboxEvent(
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload={"user_id": str(aggregate_id), **(payload or {})},
        )
    )
