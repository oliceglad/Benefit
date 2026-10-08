"""Выдача токенов в cookie.

Клиент включает режим заголовком ``X-Auth-Mode: cookie``. Тогда:

* ``benefit_access`` — access-токен: HttpOnly, SameSite=Strict, путь ``/``;
* ``benefit_refresh`` — refresh-токен: HttpOnly, SameSite=Strict, путь только
  ``/api/v1/auth`` (в остальные сервисы не уходит);
* ``benefit_csrf`` — CSRF-токен, читаемый JS: его значение передаётся в
  заголовке ``X-CSRF-Token`` в изменяющих запросах (double-submit).

Токены в теле ответа не возвращаются — скрипт на странице (XSS) их не
прочитает.
"""

import hmac
import secrets

from fastapi import Request, Response

from app.core.config import settings
from app.schemas.auth import TokenResponse

AUTH_MODE_HEADER = "x-auth-mode"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def wants_cookies(request: Request) -> bool:
    return request.headers.get(AUTH_MODE_HEADER, "").lower() == "cookie"


def _set(
    response: Response, name: str, value: str, max_age: int, **kwargs: object
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        secure=settings.cookie_secure,
        samesite="strict",
        domain=settings.cookie_domain,
        **kwargs,  # type: ignore[arg-type]
    )


def deliver(
    tokens: TokenResponse,
    request: Request,
    response: Response,
    *,
    cookie_mode: bool | None = None,
) -> TokenResponse:
    """В режиме cookie переносит токены из тела ответа в cookie.

    ``cookie_mode`` — явный выбор режима; по умолчанию — по заголовку.
    """
    if not (wants_cookies(request) if cookie_mode is None else cookie_mode):
        return tokens
    assert tokens.access_token and tokens.refresh_token
    csrf = secrets.token_urlsafe(32)
    _set(
        response,
        settings.access_cookie_name,
        tokens.access_token,
        tokens.expires_in,
        httponly=True,
        path="/",
    )
    _set(
        response,
        settings.refresh_cookie_name,
        tokens.refresh_token,
        tokens.refresh_expires_in,
        httponly=True,
        path=settings.refresh_cookie_path,
    )
    # CSRF живёт столько же, сколько сессия (refresh).
    _set(
        response,
        settings.csrf_cookie_name,
        csrf,
        tokens.refresh_expires_in,
        httponly=False,
        path="/",
    )
    return tokens.model_copy(
        update={
            "access_token": None,
            "refresh_token": None,
            "delivery": "cookie",
            "csrf_token": csrf,
        }
    )


def clear(response: Response) -> None:
    for name, path in (
        (settings.access_cookie_name, "/"),
        (settings.refresh_cookie_name, settings.refresh_cookie_path),
        (settings.csrf_cookie_name, "/"),
    ):
        response.delete_cookie(
            name,
            path=path,
            domain=settings.cookie_domain,
            secure=settings.cookie_secure,
            samesite="strict",
        )


def csrf_ok(request: Request) -> bool:
    """Double-submit: заголовок совпадает с cookie (для запросов по cookie)."""
    if request.method.upper() in SAFE_METHODS:
        return True
    expected = request.cookies.get(settings.csrf_cookie_name)
    provided = request.headers.get(settings.csrf_header_name)
    return bool(expected and provided and hmac.compare_digest(expected, provided))
