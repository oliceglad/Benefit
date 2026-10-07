"""Точка входа mail-service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health_router, router
from app.core.config import settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging(settings.log_level)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
