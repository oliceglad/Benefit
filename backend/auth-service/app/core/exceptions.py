"""Прикладные ошибки — общие для всех сервисов (benefit_common.errors)."""

from benefit_common.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)

__all__ = [
    "AppError",
    "ConflictError",
    "ForbiddenError",
    "NotFoundError",
    "ServiceUnavailableError",
    "UnauthorizedError",
]
