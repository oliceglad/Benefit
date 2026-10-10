"""Точка входа matching-service."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from benefit_common.observability import setup_app
from fastapi import FastAPI

from app.api.internal.router import router as internal_router
from app.api.v1.endpoints.talent import router as talent_router
from app.core.config import settings
from app.core.logging import SERVICE_NAME, setup_logging
from app.db.session import async_session_factory, engine
from app.services.indexer import Indexer
from app.services.source import CandidateServiceSource

logger = logging.getLogger(__name__)


async def run_indexer() -> None:
    """Первичная загрузка, затем чтение ленты событий candidate-service."""
    indexer = Indexer(async_session_factory, CandidateServiceSource())
    bootstrapped = False
    while True:
        try:
            if not bootstrapped:
                await indexer.bootstrap()
                bootstrapped = True
            while await indexer.sync_events() >= settings.sync_batch_size:
                pass
        except Exception:
            logger.exception("Index sync failed, will retry")
        await asyncio.sleep(settings.sync_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging(settings.log_level)
    async with contextlib.AsyncExitStack() as stack:
        if settings.background_jobs_enabled:
            task = asyncio.create_task(run_indexer())
            stack.callback(task.cancel)
        yield
    await engine.dispose()


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
    app.include_router(talent_router, prefix=settings.api_prefix)
    app.include_router(internal_router)
    return app


app = create_app()
