"""Профиль текущего пользователя и привязанные внешние аккаунты."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.core.exceptions import AppError, ConflictError
from app.repositories.users import ExternalIdentityRepository
from app.schemas.user import IdentityResponse, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.get("/me/identities", response_model=list[IdentityResponse])
async def list_identities(
    user: CurrentUser, session: SessionDep
) -> list[IdentityResponse]:
    """Привязанные внешние аккаунты (ФСП ID, Keycloak)."""
    identities = await ExternalIdentityRepository(session).list_for_user(user.id)
    return [IdentityResponse.model_validate(i) for i in identities]


@router.delete("/me/identities/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_identity(
    provider: str, user: CurrentUser, session: SessionDep
) -> None:
    repository = ExternalIdentityRepository(session)
    identities = await repository.list_for_user(user.id)
    identity = next((i for i in identities if i.provider == provider), None)
    if identity is None:
        raise AppError(
            "Аккаунт не привязан",
            code="not_linked",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if user.password_hash is None and len(identities) == 1:
        raise ConflictError(
            "Нельзя отвязать единственный способ входа", code="last_login_method"
        )
    await repository.delete(identity)
    await session.commit()
