"""Точка входа employer-service."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from benefit_common.observability import setup_app
from fastapi import FastAPI

from app.api.internal.router import router as internal_router
from app.api.v1.endpoints.employers import router as employers_router
from app.api.v1.endpoints.vacancies import router as vacancies_router
from app.core.config import settings
from app.core.logging import SERVICE_NAME, setup_logging
from app.db.session import async_session_factory, engine
from app.services.registry import get_registry
from app.services.verification import CompanyVerifier
from app.services.website import get_website_checker

logger = logging.getLogger(__name__)

RECHECK_INTERVAL_SECONDS = 3600


async def recheck_companies() -> None:
    """Раз в час перепроверяет по реестру компании, проверенные больше
    ``verification_recheck_days`` назад: ликвидация снимает статус."""
    while True:
        try:
            async with async_session_factory() as session:
                verifier = CompanyVerifier(
                    session, get_registry(), get_website_checker()
                )
                await verifier.recheck_stale()
        except Exception:
            logger.exception("Company recheck failed")
        await asyncio.sleep(RECHECK_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging(settings.log_level)
    task = None
    if settings.verification_recheck_enabled:
        task = asyncio.create_task(recheck_companies())
    yield
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=None,
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )
    setup_app(app, SERVICE_NAME)
    app.include_router(employers_router, prefix=settings.api_prefix)
    app.include_router(vacancies_router, prefix=settings.vacancies_prefix)
    app.include_router(internal_router)
    return app


app = create_app()
