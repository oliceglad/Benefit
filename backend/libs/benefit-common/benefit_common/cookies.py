"""Авторизация по access-токену из cookie и защита от CSRF.

Браузер отправляет cookie автоматически, поэтому изменяющий запрос,
авторизованный cookie, должен нести заголовок ``X-CSRF-Token`` со значением
cookie ``benefit_csrf`` (double-submit: чужой сайт не может прочитать cookie
и подставить заголовок). Запросы с заголовком ``Authorization`` от CSRF не
зависят и проверку не проходят.
"""

import hmac
from collections.abc import Mapping

from benefit_common.settings import get_common_settings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def access_token_from_cookie(cookies: Mapping[str, str]) -> str | None:
    return cookies.get(get_common_settings().access_cookie_name) or None


def csrf_ok(
    method: str, cookies: Mapping[str, str], headers: Mapping[str, str]
) -> bool:
    """Проверка double-submit CSRF для запроса, авторизованного cookie."""
    if method.upper() in SAFE_METHODS:
        return True
    settings = get_common_settings()
    expected = cookies.get(settings.csrf_cookie_name)
    provided = headers.get(settings.csrf_header_name.lower()) or headers.get(
        settings.csrf_header_name
    )
    return bool(expected and provided and hmac.compare_digest(expected, provided))


def origin_trusted(headers: Mapping[str, str]) -> bool:
    """Origin разрешён для авторизации по cookie (браузерный WebSocket)."""
    origin = headers.get("origin")
    return origin is None or origin in get_common_settings().trusted_origins
