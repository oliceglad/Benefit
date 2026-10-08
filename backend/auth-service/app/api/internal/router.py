"""Внутренний API для других сервисов. Через шлюз наружу не публикуется,
дополнительно защищён межсервисным токеном."""

import hmac
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.repositories.users import ExternalIdentityRepository
from app.schemas.user import InternalIdentityResponse


def verify_internal_token(x_internal_token: Annotated[str, Header()] = "") -> None:
    if not hmac.compare_digest(x_internal_token, settings.internal_api_token):
        raise UnauthorizedError("Неверный межсервисный токен")


router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)


@router.get(
    "/users/{user_id}/identities", response_model=list[InternalIdentityResponse]
)
async def user_identities(
    user_id: uuid.UUID, session: SessionDep
) -> list[InternalIdentityResponse]:
    identities = await ExternalIdentityRepository(session).list_for_user(user_id)
    return [InternalIdentityResponse.model_validate(i) for i in identities]
