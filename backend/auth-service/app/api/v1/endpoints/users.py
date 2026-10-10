"""Аккаунт текущего пользователя: профиль, пароль, почта, внешние
аккаунты, удаление."""

from fastapi import APIRouter, Request, Response, status

from app.api.deps import AccountServiceDep, CurrentUser, SessionDep
from app.core import cookies
from app.core.config import settings
from app.core.exceptions import AppError, ConflictError
from app.repositories.users import ExternalIdentityRepository
from app.schemas.account import (
    AccountDelete,
    CodeConfirm,
    CodeSent,
    EmailChangeRequest,
    PasswordChange,
    ProfileUpdate,
)
from app.schemas.auth import TokenResponse
from app.schemas.user import IdentityResponse, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


def _cookie_session(request: Request) -> bool:
    """Сессия в cookie: новые токены тоже отдаём в cookie."""
    return cookies.wants_cookies(request) or (
        settings.access_cookie_name in request.cookies
        and "authorization" not in request.headers
    )


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: ProfileUpdate, user: CurrentUser, service: AccountServiceDep
) -> UserResponse:
    """Редактирование аккаунта (имя). Почта меняется через ``/me/email``."""
    if "full_name" in data.model_fields_set:
        user = await service.update_profile(user, data.full_name)
    return UserResponse.model_validate(user)


@router.post("/me/password", response_model=TokenResponse)
async def change_password(
    data: PasswordChange,
    user: CurrentUser,
    service: AccountServiceDep,
    request: Request,
    response: Response,
) -> TokenResponse:
    """Смена пароля (нужен текущий). Остальные сессии завершаются, текущая
    получает новые токены. Аккаунт без пароля задаёт его через
    ``/auth/password/forgot``."""
    tokens = await service.change_password(
        user, data.current_password, data.new_password
    )
    return cookies.deliver(
        tokens, request, response, cookie_mode=_cookie_session(request)
    )


@router.post("/me/email", response_model=CodeSent, status_code=status.HTTP_202_ACCEPTED)
async def request_email_change(
    data: EmailChangeRequest, user: CurrentUser, service: AccountServiceDep
) -> CodeSent:
    """Смена почты, шаг 1: код придёт на новый адрес. Если у аккаунта есть
    пароль, он обязателен."""
    return await service.request_email_change(
        user, data.normalized_email(), data.password
    )


@router.post("/me/email/confirm", response_model=TokenResponse)
async def confirm_email_change(
    data: CodeConfirm,
    user: CurrentUser,
    service: AccountServiceDep,
    request: Request,
    response: Response,
) -> TokenResponse:
    """Смена почты, шаг 2: код из письма. Возвращает новые токены (почта
    в токене изменилась), остальные сессии завершаются."""
    tokens = await service.confirm_email_change(user, data.code)
    return cookies.deliver(
        tokens, request, response, cookie_mode=_cookie_session(request)
    )


@router.post(
    "/me/delete-code", response_model=CodeSent, status_code=status.HTTP_202_ACCEPTED
)
async def send_deletion_code(user: CurrentUser, service: AccountServiceDep) -> CodeSent:
    """Код подтверждения удаления на почту (для аккаунтов без пароля; с
    паролем можно подтвердить и им)."""
    return await service.send_deletion_code(user)


@router.post("/me/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    data: AccountDelete,
    user: CurrentUser,
    service: AccountServiceDep,
    response: Response,
) -> None:
    """Удаление аккаунта без возможности восстановления.

    Профиль, компания, отклики, переписка, уведомления и результаты тестов
    удаляются во всех сервисах (асинхронно, с повторами). Cookie сессии
    очищаются.
    """
    await service.delete(user, data.password, data.code)
    cookies.clear(response)


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
