"""Данные кандидата из candidate-service."""

import uuid
from typing import Any, Protocol

from benefit_common.internal import InternalClient, raise_for_client_error

from app.core.config import settings


class CandidateDirectory(Protocol):
    async def snapshot(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        """Профиль кандидата для тестирования или ``None``, если его нет."""
        ...


class CandidateServiceClient:
    def __init__(self) -> None:
        self.client = InternalClient(
            settings.candidate_service_url, service="candidate"
        )

    async def snapshot(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        response = await self.client.get(f"/internal/v1/candidates/{user_id}")
        if response.status_code == 404:
            return None
        raise_for_client_error(response)
        return response.json()["data"]


def get_candidate_directory() -> CandidateDirectory:
    return CandidateServiceClient()
