"""Точка входа chat-service."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from benefit_common.observability import setup_app
from fastapi import FastAPI

from app.api.internal.router import router as internal_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.tasks import router as tasks_router
from app.api.v1.endpoints.ws import router as ws_router
from app.core.config import settings
from app.core.logging import SERVICE_NAME, setup_logging
from app.db.session import async_session_factory, engine
from app.services.chat import ChatService
from app.services.delivery import build_relay
from app.services.events import resolve_event
from app.services.realtime import hub
from app.services.storage import get_storage
from app.services.tasks import TaskService

logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    """Просрочка и повтор заданий, напоминания, очистка брошенных файлов."""
    while True:
        try:
            async with async_session_factory() as session:
                chat = ChatService(session, get_storage())
                await TaskService(session, chat).run_scheduled()
                await chat.cleanup_orphans()
        except Exception:
            logger.exception("Chat scheduler iteration failed")
        await asyncio.sleep(settings.scheduler_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging(settings.log_level)
    settings.files_dir.mkdir(parents=True, exist_ok=True)
    hub.resolver = resolve_event
    async with contextlib.AsyncExitStack() as stack:
        if settings.background_jobs_enabled:
            await hub.start()
            stack.push_async_callback(hub.stop)
            await stack.enter_async_context(
                build_relay(async_session_factory).running()
            )
            scheduler = asyncio.create_task(run_scheduler())
            stack.callback(scheduler.cancel)
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
    app.include_router(chat_router, prefix=settings.api_prefix)
    app.include_router(tasks_router, prefix=settings.api_prefix)
    app.include_router(ws_router, prefix=settings.api_prefix)
    app.include_router(internal_router)
    return app


app = create_app()
