"""Общие зависимости FastAPI."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.employers import EmployerService
from app.services.matching import ContactDirectory, Matcher, get_contacts, get_matcher

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_employer_service(session: SessionDep) -> EmployerService:
    return EmployerService(session)


EmployerServiceDep = Annotated[EmployerService, Depends(get_employer_service)]
MatcherDep = Annotated[Matcher, Depends(get_matcher)]
ContactsDep = Annotated[ContactDirectory, Depends(get_contacts)]
