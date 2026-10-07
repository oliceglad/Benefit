"""Регистрация и вход по почте и паролю, управление сессиями."""

from fastapi import APIRouter, status

from app.api.deps import AuthServiceDep, TokenServiceDep
from app.schemas.auth import (
    EmailRequest,
    LoginRequest,
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
    data: VerifyEmailRequest, service: AuthServiceDep
) -> TokenResponse:
    """Подтверждение почты кодом из письма. Сразу выполняет вход."""
    return await service.verify_email(data.email, data.code)


@router.post("/resend-code", status_code=status.HTTP_202_ACCEPTED)
async def resend_code(data: EmailRequest, service: AuthServiceDep) -> None:
    """Повторная отправка кода подтверждения."""
    await service.resend_code(data.email)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.login(data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, tokens: TokenServiceDep) -> TokenResponse:
    """Обмен refresh-токена на новую пару (старый refresh-токен отзывается)."""
    return await tokens.rotate(data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, tokens: TokenServiceDep) -> None:
    await tokens.revoke(data.refresh_token)
