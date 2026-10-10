"""Общие зависимости FastAPI."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.employers import EmployerService
from app.services.matching import ContactDirectory, Matcher, get_contacts, get_matcher
from app.services.registry import CompanyRegistry, get_registry
from app.services.verification import CompanyVerifier
from app.services.website import WebsiteChecker, get_website_checker

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_employer_service(session: SessionDep) -> EmployerService:
    return EmployerService(session)


EmployerServiceDep = Annotated[EmployerService, Depends(get_employer_service)]


def get_verifier(
    session: SessionDep,
    registry: Annotated[CompanyRegistry, Depends(get_registry)],
    website: Annotated[WebsiteChecker, Depends(get_website_checker)],
) -> CompanyVerifier:
    return CompanyVerifier(session, registry, website)


VerifierDep = Annotated[CompanyVerifier, Depends(get_verifier)]
MatcherDep = Annotated[Matcher, Depends(get_matcher)]
ContactsDep = Annotated[ContactDirectory, Depends(get_contacts)]
