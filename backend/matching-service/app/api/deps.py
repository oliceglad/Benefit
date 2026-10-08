"""Общие зависимости FastAPI."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.talent import TalentService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_talent_service(session: SessionDep) -> TalentService:
    return TalentService(session)


TalentServiceDep = Annotated[TalentService, Depends(get_talent_service)]
