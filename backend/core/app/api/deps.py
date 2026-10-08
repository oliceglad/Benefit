"""Общие зависимости FastAPI для эндпоинтов."""

from typing import Annotated

from benefit_common.security import (
    Candidate,
    CurrentPrincipal,
    Employer,
    Principal,
    Role,
    require_roles,
)
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

__all__ = [
    "Candidate",
    "CurrentPrincipal",
    "Employer",
    "Principal",
    "Role",
    "SessionDep",
    "require_roles",
]
