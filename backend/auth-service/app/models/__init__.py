"""ORM-модели предметной области.

Каждую новую модель нужно импортировать здесь, чтобы она попала
в ``Base.metadata`` и была видна Alembic при autogenerate.
"""

from app.db.base import Base
from app.models.external_identity import ExternalIdentity
from app.models.tokens import (
    EmailVerificationCode,
    OAuthLoginCode,
    OAuthState,
    RefreshToken,
)
from app.models.user import User, UserRole

__all__ = [
    "Base",
    "EmailVerificationCode",
    "ExternalIdentity",
    "OAuthLoginCode",
    "OAuthState",
    "RefreshToken",
    "User",
    "UserRole",
]
