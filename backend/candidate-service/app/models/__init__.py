"""ORM-модели предметной области.

Каждую новую модель нужно импортировать здесь, чтобы она попала
в ``Base.metadata`` и была видна Alembic при autogenerate.
"""

from app.db.base import Base
from app.models.candidate import (
    CandidateActivity,
    CandidatePhoto,
    CandidateProfile,
    Consent,
    ContactGrant,
    FspAchievement,
    OutboxEvent,
    ProfileStatus,
)

__all__ = [
    "Base",
    "CandidateActivity",
    "CandidatePhoto",
    "CandidateProfile",
    "Consent",
    "ContactGrant",
    "FspAchievement",
    "OutboxEvent",
    "ProfileStatus",
]
