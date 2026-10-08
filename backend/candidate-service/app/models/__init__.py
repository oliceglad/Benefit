"""ORM-модели предметной области.

Каждую новую модель нужно импортировать здесь, чтобы она попала
в ``Base.metadata`` и была видна Alembic при autogenerate.
"""

from app.db.base import Base
from app.models.candidate import (
    CandidatePhoto,
    CandidateProfile,
    Consent,
    FspAchievement,
    OutboxEvent,
    ProfileStatus,
)

__all__ = [
    "Base",
    "CandidatePhoto",
    "CandidateProfile",
    "Consent",
    "FspAchievement",
    "OutboxEvent",
    "ProfileStatus",
]
