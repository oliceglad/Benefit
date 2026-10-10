"""ORM-модели предметной области.

Каждую новую модель нужно импортировать здесь, чтобы она попала
в ``Base.metadata`` и была видна Alembic при autogenerate.
"""

from app.db.base import Base
from app.models.external_identity import ExternalIdentity
from app.models.outbox import OutboxMessage
from app.models.tokens import (
    CodePurpose,
    EmailVerificationCode,
    OAuthLoginCode,
    OAuthState,
    RefreshToken,
)
from app.models.user import User, UserRole

__all__ = [
    "Base",
    "CodePurpose",
    "EmailVerificationCode",
    "ExternalIdentity",
    "OAuthLoginCode",
    "OAuthState",
    "OutboxMessage",
    "RefreshToken",
    "User",
    "UserRole",
]
