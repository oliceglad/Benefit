"""Асинхронный движок SQLAlchemy и фабрика сессий."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    # SQL-логи с параметрами — только при локальной отладке.
    echo=settings.debug and settings.app_env == "local",
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Открывает сессию БД на время обработки одного запроса."""
    async with async_session_factory() as session:
        yield session
