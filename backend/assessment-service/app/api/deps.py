"""Общие зависимости FastAPI."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.attempts import AttemptService
from app.services.candidates import CandidateDirectory, get_candidate_directory

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_attempt_service(
    session: SessionDep,
    candidates: Annotated[CandidateDirectory, Depends(get_candidate_directory)],
) -> AttemptService:
    return AttemptService(session, candidates)


AttemptServiceDep = Annotated[AttemptService, Depends(get_attempt_service)]
