"""Точка входа employer-service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from benefit_common.errors import register_exception_handlers
from fastapi import FastAPI

from app.api.internal.router import router as internal_router
from app.api.v1.endpoints.employers import router as employers_router
from app.api.v1.endpoints.vacancies import router as vacancies_router
from app.core.config import settings
from app.core.logging import setup_logging
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
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=None,
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )
    register_exception_handlers(app)
    app.include_router(employers_router, prefix=settings.api_prefix)
    app.include_router(vacancies_router, prefix=settings.vacancies_prefix)
    app.include_router(internal_router)
    return app


app = create_app()
