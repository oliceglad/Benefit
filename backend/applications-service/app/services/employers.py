"""Данные работодателя из employer-service: компания и вакансии."""

import uuid
from typing import Any, Protocol

from benefit_common.internal import InternalClient, raise_for_client_error

from app.core.config import settings


class EmployerDirectory(Protocol):
    async def company(self, owner_id: uuid.UUID) -> dict[str, Any] | None: ...

    async def vacancy(self, vacancy_id: uuid.UUID) -> dict[str, Any] | None: ...


class EmployerServiceClient:
    def __init__(self) -> None:
        self.client = InternalClient(settings.employer_service_url, service="employer")

    async def _get(self, path: str) -> dict[str, Any] | None:
        response = await self.client.get(path)
        if response.status_code == 404:
            return None
        raise_for_client_error(response)
        return response.json()

    async def company(self, owner_id: uuid.UUID) -> dict[str, Any] | None:
        return await self._get(f"/internal/v1/companies/by-owner/{owner_id}")

    async def vacancy(self, vacancy_id: uuid.UUID) -> dict[str, Any] | None:
        return await self._get(f"/internal/v1/vacancies/{vacancy_id}")


def get_employer_directory() -> EmployerDirectory:
    return EmployerServiceClient()
