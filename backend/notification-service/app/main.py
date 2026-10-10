"""Точка входа notification-service."""

import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from benefit_common.observability import setup_app
from fastapi import APIRouter, FastAPI

from app.api.internal.router import router as internal_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.core.config import settings
from app.core.logging import SERVICE_NAME, setup_logging
from app.db.session import async_session_factory, engine
from app.services.delivery import build_relay


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging(settings.log_level)
    async with contextlib.AsyncExitStack() as stack:
        if settings.outbox_relay_enabled:
            await stack.enter_async_context(
                build_relay(async_session_factory).running()
            )
        yield
    await engine.dispose()


health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    # В production документация API не публикуется.
    public_docs = settings.app_env != "production"
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url=f"{settings.api_prefix}/docs" if public_docs else None,
        redoc_url=None,
        openapi_url=f"{settings.api_prefix}/openapi.json" if public_docs else None,
    )
    setup_app(app, SERVICE_NAME)
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(notifications_router, prefix=settings.api_prefix)
    app.include_router(internal_router)
    return app


app = create_app()
