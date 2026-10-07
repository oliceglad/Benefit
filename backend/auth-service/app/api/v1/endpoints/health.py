"""Эндпоинты проверки состояния сервиса."""

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep
from app.schemas.health import DatabaseHealthResponse, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: приложение запущено и отвечает."""
    return HealthResponse()


@router.get("/db", response_model=DatabaseHealthResponse)
async def health_db(
    session: SessionDep,
    response: Response,
) -> DatabaseHealthResponse:
    """Readiness: БД доступна."""
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        logger.exception("Database health check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return DatabaseHealthResponse(status="unavailable")

    return DatabaseHealthResponse(status="ok")
