"""Вход через внешних OIDC-провайдеров: ФСП ID и Keycloak."""

import logging
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUser, OAuthServiceDep, ProviderRegistryDep
from app.core import cookies
from app.core.config import settings
from app.core.exceptions import AppError
from app.models.user import SelfServiceRole
from app.schemas.auth import (
    AuthorizationUrlResponse,
    OAuthExchangeRequest,
    ProviderInfo,
    TokenResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["oauth"])


def _frontend_redirect(**params: str) -> RedirectResponse:
    url = settings.oauth_callback_redirect_url
    separator = "&" if "?" in url else "?"
    return RedirectResponse(
        f"{url}{separator}{urlencode(params)}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers(registry: ProviderRegistryDep) -> list[ProviderInfo]:
    """Включённые внешние провайдеры — для кнопок «Войти через …»."""
    return [ProviderInfo(id=p.id, name=p.config.name) for p in registry.all()]


@router.get("/oauth/{provider}/authorize")
async def authorize(
    provider: str,
    service: OAuthServiceDep,
    request: Request,
    role: Annotated[
        SelfServiceRole | None,
        Query(description="Роль для нового аккаунта, если её не передал провайдер"),
    ] = None,
) -> RedirectResponse:
    """Перенаправляет браузер на страницу входа провайдера."""
    redirect = RedirectResponse("", status_code=status.HTTP_302_FOUND)
    browser_id = cookies.ensure_oauth_browser_id(request, redirect)
    redirect.headers["location"] = await service.start(provider, browser_id, role)
    return redirect


@router.post("/oauth/{provider}/link", response_model=AuthorizationUrlResponse)
async def link(
    provider: str,
    user: CurrentUser,
    service: OAuthServiceDep,
    request: Request,
    response: Response,
) -> AuthorizationUrlResponse:
    """Привязка внешнего аккаунта (например, ФСП ID) к текущему пользователю.

    Фронтенд перенаправляет браузер на ``authorization_url``; после входа
    у провайдера браузер вернётся на фронтенд с ``?linked=<provider>``.
    """
    browser_id = cookies.ensure_oauth_browser_id(request, response)
    url = await service.start(provider, browser_id, link_user_id=user.id)
    return AuthorizationUrlResponse(authorization_url=url)


@router.get("/oauth/{provider}/callback", include_in_schema=False)
async def callback(
    provider: str,
    service: OAuthServiceDep,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Возврат от провайдера. Браузер уходит на фронтенд с одноразовым
    ``code`` (или ``error``), который фронтенд меняет на токены."""
    if error:
        return _frontend_redirect(error=error)
    if not code or not state:
        return _frontend_redirect(error="invalid_request")
    try:
        result = await service.complete(
            provider, code, state, cookies.oauth_browser_id(request)
        )
    except AppError as exc:
        logger.info("OAuth login via %s failed: %s", provider, exc.code)
        return _frontend_redirect(error=exc.code)
    if result.linked:
        return _frontend_redirect(linked=provider)
    assert result.login_code is not None
    return _frontend_redirect(code=result.login_code)


@router.post("/oauth/exchange", response_model=TokenResponse)
async def exchange(
    data: OAuthExchangeRequest,
    service: OAuthServiceDep,
    request: Request,
    response: Response,
) -> TokenResponse:
    """Обмен одноразового кода входа на пару токенов
    (``X-Auth-Mode: cookie`` — в cookie)."""
    tokens = await service.exchange(data.code, cookies.oauth_browser_id(request))
    return cookies.deliver(tokens, request, response)


@router.get("/oauth-dev-callback", response_model=None, include_in_schema=False)
async def dev_callback(
    service: OAuthServiceDep,
    request: Request,
    code: str | None = None,
    error: str | None = None,
    linked: str | None = None,
) -> TokenResponse | dict[str, str]:
    """Заглушка страницы фронтенда для локальной разработки:
    сразу меняет код на токены и показывает их."""
    if settings.app_env != "local":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if linked:
        return {"linked": linked}
    if error or not code:
        raise AppError(f"Вход не выполнен: {error}", code=error or "invalid_request")
    return await service.exchange(code, cookies.oauth_browser_id(request))
