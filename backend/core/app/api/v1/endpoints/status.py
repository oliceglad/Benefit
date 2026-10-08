"""Состояние платформы: какие сервисы работают, какие нет."""

import asyncio
import time
from typing import Literal

import httpx
from benefit_common.context import service_title
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/status", tags=["health"])

TIMEOUT_SECONDS = 3.0


class ServiceStatus(BaseModel):
    service: str
    title: str
    status: Literal["ok", "degraded", "down"]
    latency_ms: int | None
    detail: str | None = None


class PlatformStatus(BaseModel):
    status: Literal["ok", "degraded", "down"]
    services: list[ServiceStatus]


async def _check(client: httpx.AsyncClient, name: str, url: str) -> ServiceStatus:
    started = time.perf_counter()
    try:
        response = await client.get(url)
    except httpx.TimeoutException:
        return ServiceStatus(
            service=name,
            title=service_title(name),
            status="down",
            latency_ms=None,
            detail="Не отвечает",
        )
    except httpx.HTTPError:
        return ServiceStatus(
            service=name,
            title=service_title(name),
            status="down",
            latency_ms=None,
            detail="Недоступен",
        )
    latency = round((time.perf_counter() - started) * 1000)
    healthy = response.status_code == 200
    return ServiceStatus(
        service=name,
        title=service_title(name),
        status="ok" if healthy else "degraded",
        latency_ms=latency,
        detail=None if healthy else f"Ответ {response.status_code}",
    )


@router.get("", response_model=PlatformStatus)
async def platform_status() -> PlatformStatus:
    """Опрашивает health-эндпоинты всех сервисов параллельно."""
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        services = await asyncio.gather(
            *(
                _check(client, name, url)
                for name, url in settings.status_services.items()
            )
        )
    states = {s.status for s in services}
    overall = "ok" if states == {"ok"} else "down" if states == {"down"} else "degraded"
    return PlatformStatus(status=overall, services=list(services))
