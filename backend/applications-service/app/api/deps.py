"""Общие зависимости FastAPI."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.candidates import CandidateDirectory, get_candidate_directory
from app.services.employers import EmployerDirectory, get_employer_directory
from app.services.invitations import InvitationService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_invitation_service(
    session: SessionDep,
    candidates: Annotated[CandidateDirectory, Depends(get_candidate_directory)],
    employers: Annotated[EmployerDirectory, Depends(get_employer_directory)],
) -> InvitationService:
    return InvitationService(session, candidates, employers)


InvitationServiceDep = Annotated[InvitationService, Depends(get_invitation_service)]
