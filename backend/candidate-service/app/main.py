"""Точка входа candidate-service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from benefit_common.observability import setup_app
from fastapi import FastAPI

from app.api.internal.router import router as internal_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import SERVICE_NAME, setup_logging
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging(settings.log_level)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        # Под префиксом сервиса, чтобы документация была доступна через шлюз.
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=None,
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )
    setup_app(app, SERVICE_NAME)
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(internal_router)
    return app


app = create_app()
