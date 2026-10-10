"""Точка входа assessment-service."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from benefit_common.observability import setup_app
from fastapi import FastAPI

from app.api.internal.router import router as internal_router
from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.assessments import router as assessments_router
from app.api.v1.endpoints.employer_tests import router as employer_tests_router
from app.core.config import settings
from app.core.logging import SERVICE_NAME, setup_logging
from app.db.session import async_session_factory, engine
from app.services.attempts import AttemptService
from app.services.candidates import CandidateServiceClient
from app.services.delivery import build_relay
from app.services.employer_tests import ChatServiceClient, EmployerTestService

logger = logging.getLogger(__name__)

EXPIRE_INTERVAL_SECONDS = 30


async def expire_overdue_attempts() -> None:
    """Фоново завершает брошенные попытки, чтобы результат не «зависал»."""
    while True:
        try:
            async with async_session_factory() as session:
                attempts = AttemptService(session, CandidateServiceClient())
                await attempts.expire_overdue()
                await EmployerTestService(
                    session, ChatServiceClient(), attempts
                ).expire_overdue()
        except Exception:
            logger.exception("Failed to expire overdue attempts")
        await asyncio.sleep(EXPIRE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging(settings.log_level)
    async with contextlib.AsyncExitStack() as stack:
        if settings.outbox_relay_enabled:
            await stack.enter_async_context(
                build_relay(async_session_factory).running()
            )
            task = asyncio.create_task(expire_overdue_attempts())
            stack.callback(task.cancel)
        yield
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
    app.include_router(assessments_router, prefix=settings.api_prefix)
    app.include_router(admin_router, prefix=settings.api_prefix)
    app.include_router(employer_tests_router, prefix=settings.api_prefix)
    app.include_router(internal_router)
    return app


app = create_app()
