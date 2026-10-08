"""Источник данных — candidate-service (лента событий и документы)."""

import uuid
from typing import Any, Protocol

from benefit_common.internal import InternalClient, raise_for_client_error

from app.core.config import settings


class CandidateSource(Protocol):
    async def events(self, after_id: int, limit: int) -> list[dict[str, Any]]: ...

    async def document(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        """Поисковый документ или ``None`` (профиль не опубликован/удалён)."""
        ...

    async def published_ids(self, offset: int, limit: int) -> list[uuid.UUID]: ...


class CandidateServiceSource:
    def __init__(self) -> None:
        self.client = InternalClient(
            settings.candidate_service_url, service="candidate"
        )

    async def events(self, after_id: int, limit: int) -> list[dict[str, Any]]:
        response = await self.client.get(
            "/internal/v1/events", params={"after_id": after_id, "limit": limit}
        )
        raise_for_client_error(response)
        return response.json()

    async def document(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        response = await self.client.get(
            f"/internal/v1/candidates/{user_id}/search-document"
        )
        if response.status_code == 404:
            return None
        raise_for_client_error(response)
        return response.json()

    async def published_ids(self, offset: int, limit: int) -> list[uuid.UUID]:
        response = await self.client.get(
            "/internal/v1/candidates",
            params={"only_published": True, "offset": offset, "limit": limit},
        )
        raise_for_client_error(response)
        return [uuid.UUID(item["user_id"]) for item in response.json()]


def get_source() -> CandidateSource:
    return CandidateServiceSource()
