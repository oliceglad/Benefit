"""Точка входа FastAPI-приложения."""

import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from benefit_common.observability import setup_app
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.internal.router import router as internal_router
from app.api.v1.router import api_router
from app.api.well_known import router as well_known_router
from app.core.config import settings
from app.core.jwt import get_keys
from app.core.logging import SERVICE_NAME, setup_logging
from app.db.session import async_session_factory, engine
from app.services.deletion import build_relay


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Действия при запуске и остановке приложения."""
    setup_logging(settings.log_level)
    # Загружаем (или создаём) ключ подписи заранее, а не на первом запросе.
    get_keys()
    async with contextlib.AsyncExitStack() as stack:
        if settings.outbox_relay_enabled:
            # Доставка событий удаления аккаунта в другие сервисы.
            await stack.enter_async_context(
                build_relay(async_session_factory).running()
            )
        yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Создаёт и настраивает экземпляр приложения."""
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        # Под префиксом auth, чтобы документация была доступна через шлюз.
        docs_url=f"{settings.api_v1_prefix}/auth/docs",
        redoc_url=None,
        openapi_url=f"{settings.api_v1_prefix}/auth/openapi.json",
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    setup_app(app, SERVICE_NAME)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(well_known_router)
    app.include_router(internal_router)
    return app


app = create_app()
