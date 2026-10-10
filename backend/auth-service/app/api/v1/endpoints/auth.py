"""Регистрация и вход по почте и паролю, управление сессиями."""

from fastapi import APIRouter, Request, Response, status

from app.api.deps import AccountServiceDep, AuthServiceDep, TokenServiceDep
from app.core import cookies
from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.schemas.auth import (
    EmailRequest,
    LoginRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(data: RegisterRequest, service: AuthServiceDep) -> RegisterResponse:
    """Регистрация кандидата или работодателя. На почту уходит код подтверждения."""
    return await service.register(data)


@router.post("/verify-email", response_model=TokenResponse)
async def verify_email(
    data: VerifyEmailRequest,
    service: AuthServiceDep,
    request: Request,
    response: Response,
) -> TokenResponse:
    """Подтверждение почты кодом из письма. Сразу выполняет вход.

    С заголовком ``X-Auth-Mode: cookie`` токены выставляются в cookie.
    """
    tokens = await service.verify_email(data.email, data.code)
    return cookies.deliver(tokens, request, response)


@router.post("/resend-code", status_code=status.HTTP_202_ACCEPTED)
async def resend_code(data: EmailRequest, service: AuthServiceDep) -> None:
    """Повторная отправка кода подтверждения."""
    await service.resend_code(data.email)


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(data: EmailRequest, service: AccountServiceDep) -> None:
    """Восстановление пароля: код придёт на почту.

    Ответ одинаковый для любых адресов — наличие аккаунта не раскрывается.
    Подходит и для аккаунтов без пароля (вход через ФСП ID): так пароль
    задаётся впервые.
    """
    await service.forgot_password(data.email)


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    data: PasswordResetRequest, service: AccountServiceDep
) -> None:
    """Новый пароль по коду из письма. Все сессии завершаются — после
    сброса нужно войти заново."""
    await service.reset_password(data.email, data.code, data.new_password)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    service: AuthServiceDep,
    request: Request,
    response: Response,
) -> TokenResponse:
    """Вход. С заголовком ``X-Auth-Mode: cookie`` токены — в HttpOnly-cookie."""
    tokens = await service.login(data.email, data.password)
    return cookies.deliver(tokens, request, response)


def _refresh_token(data: RefreshRequest | None, request: Request) -> str:
    """Refresh-токен из тела или (в режиме cookie) из cookie — с CSRF."""
    if data is not None and data.refresh_token:
        return data.refresh_token
    token = request.cookies.get(settings.refresh_cookie_name)
    if not token:
        raise UnauthorizedError("Нет refresh-токена", code="invalid_refresh_token")
    if not cookies.csrf_ok(request):
        raise ForbiddenError("CSRF-токен отсутствует или неверен", code="csrf_failed")
    return token


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    tokens: TokenServiceDep,
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
) -> TokenResponse:
    """Обмен refresh-токена на новую пару (старый refresh-токен отзывается).

    Токен берётся из тела или из cookie ``benefit_refresh``.
    """
    from_cookie = not (data and data.refresh_token)
    pair = await tokens.rotate(_refresh_token(data, request))
    # Обновление по cookie — новые токены тоже в cookie.
    return cookies.deliver(
        pair,
        request,
        response,
        cookie_mode=from_cookie or cookies.wants_cookies(request),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    tokens: TokenServiceDep,
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
) -> None:
    """Отзывает refresh-токен (из тела или cookie) и удаляет cookie."""
    if (data and data.refresh_token) or request.cookies.get(
        settings.refresh_cookie_name
    ):
        await tokens.revoke(_refresh_token(data, request))
    cookies.clear(response)
