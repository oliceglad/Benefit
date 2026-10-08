"""Ошибки и единый формат ответа.

Любая ошибка любого сервиса возвращается так::

    {"error": {
        "code": "conversation_closed",           # машиночитаемый код
        "message": "Переписка закрыта: ...",     # понятное человеку описание
        "service": "chat-service",               # где ошибка произошла
        "request_id": "4f1c…",                   # сквозной ID для поиска в логах
        "details": [{"field": "...", "message": "..."}]   # для ошибок валидации
    }}

Если упал соседний сервис, ``service`` указывает на него, а не на сервис,
который вернул ответ.
"""

import logging
import re
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from benefit_common.context import (
    current_request_id,
    current_service,
    service_title,
)

logger = logging.getLogger("benefit.errors")


class AppError(Exception):
    """Ошибка бизнес-логики с машиночитаемым кодом."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "Некорректный запрос"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
        service: str | None = None,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.headers = headers
        # Сервис, где ошибка произошла (по умолчанию — текущий).
        self.service = service
        self.details = details
        super().__init__(self.message)


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Требуется вход в систему"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "Недостаточно прав"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Не найдено"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"
    message = "Сервис временно недоступен"


def error_body(
    code: str,
    message: str,
    *,
    service: str | None = None,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "service": service or current_service(),
        "request_id": current_request_id(),
    }
    if details:
        error["details"] = details
    return {"error": error}


def _response(
    status_code: int,
    code: str,
    message: str,
    *,
    service: str | None = None,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_body(code, message, service=service, details=details),
        headers=headers,
    )


# --- Понятные сообщения для ошибок валидации ----------------------------------

VALIDATION_MESSAGES = {
    "missing": "обязательное поле",
    "extra_forbidden": "неизвестное поле",
    "string_too_short": "слишком короткое значение (минимум {min_length})",
    "string_too_long": "слишком длинное значение (максимум {max_length})",
    "string_pattern_mismatch": "неверный формат",
    "string_type": "ожидается строка",
    "too_short": "слишком мало элементов (минимум {min_length})",
    "too_long": "слишком много элементов (максимум {max_length})",
    "greater_than_equal": "значение должно быть не меньше {ge}",
    "greater_than": "значение должно быть больше {gt}",
    "less_than_equal": "значение должно быть не больше {le}",
    "less_than": "значение должно быть меньше {lt}",
    "int_parsing": "ожидается целое число",
    "int_type": "ожидается целое число",
    "float_parsing": "ожидается число",
    "bool_parsing": "ожидается true или false",
    "uuid_parsing": "некорректный идентификатор",
    "date_parsing": "некорректная дата (формат ГГГГ-ММ-ДД)",
    "date_from_datetime_parsing": "некорректная дата (формат ГГГГ-ММ-ДД)",
    "datetime_parsing": "некорректные дата и время",
    "datetime_from_date_parsing": "некорректные дата и время",
    "url_parsing": "некорректная ссылка",
    "url_scheme": "ссылка должна начинаться с http:// или https://",
    "json_invalid": "некорректный JSON",
    "list_type": "ожидается список",
    "dict_type": "ожидается объект",
    "model_type": "ожидается объект",
    "enum": "допустимые значения: {expected}",
    "literal_error": "допустимые значения: {expected}",
}

LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}


def _field(loc: tuple[Any, ...]) -> str:
    parts = [p for p in loc if p not in LOCATION_PREFIXES]
    path = ""
    for part in parts:
        path += (
            f"[{part}]" if isinstance(part, int) else f".{part}" if path else str(part)
        )
    return path or "запрос"


def _validation_message(error: dict[str, Any]) -> str:
    error_type = error.get("type", "")
    if error_type == "value_error":
        message = str(error.get("msg", ""))
        message = message.removeprefix("Value error, ")
        if "email address" in message:
            return "некорректный адрес почты"
        return message
    template = VALIDATION_MESSAGES.get(error_type)
    if template is None:
        return str(error.get("msg", "некорректное значение"))
    if error_type in ("enum", "literal_error"):
        # Значения enum/Literal из текста pydantic → «candidate, employer».
        values = re.findall(
            r"'([^']*)'", str((error.get("ctx") or {}).get("expected", ""))
        )
        if values:
            return f"допустимые значения: {', '.join(values)}"
    try:
        return template.format(**(error.get("ctx") or {}))
    except (KeyError, IndexError):
        return template.split(" (")[0]


def validation_details(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"field": _field(tuple(e.get("loc", ()))), "message": _validation_message(e)}
        for e in errors
    ]


# --- Обработчики ---------------------------------------------------------------

HTTP_MESSAGES = {
    400: ("bad_request", "Некорректный запрос"),
    401: ("unauthorized", "Требуется вход в систему"),
    403: ("forbidden", "Недостаточно прав"),
    404: ("not_found", "Ресурс не найден — проверьте адрес запроса"),
    405: ("method_not_allowed", "Этот метод не поддерживается для данного адреса"),
    413: ("payload_too_large", "Слишком большой запрос или файл"),
    415: ("unsupported_media_type", "Неподдерживаемый формат данных"),
    429: ("rate_limited", "Слишком много запросов, попробуйте позже"),
}


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    if exc.status_code >= 500:
        logger.warning(
            "%s: %s (service=%s)",
            exc.code,
            exc.message,
            exc.service or current_service(),
        )
    return _response(
        exc.status_code,
        exc.code,
        exc.message,
        service=exc.service,
        details=exc.details,
        headers=exc.headers,
    )


async def http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code, default = HTTP_MESSAGES.get(exc.status_code, ("http_error", "Ошибка запроса"))
    detail = exc.detail if isinstance(exc.detail, str) else None
    # Стандартные английские тексты Starlette заменяем понятными.
    if detail is None or detail in (
        "Not Found",
        "Method Not Allowed",
        "Unauthorized",
        "Forbidden",
        "Not authenticated",
        "Bad Request",
    ):
        detail = default
    return _response(
        exc.status_code, code, detail, headers=getattr(exc, "headers", None)
    )


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = validation_details(list(exc.errors()))
    fields = ", ".join(dict.fromkeys(d["field"] for d in details))
    return _response(
        422,
        "validation_error",
        f"Проверьте данные: {fields}",
        details=details,
    )


async def database_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Database error")
    return _response(
        503,
        "database_unavailable",
        f"База данных недоступна ({service_title(current_service())}). "
        "Попробуйте повторить запрос позже",
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, ConnectionRefusedError | TimeoutError):
        return await database_error_handler(_, exc)
    logger.exception("Unhandled error")
    request_id = current_request_id()
    return _response(
        500,
        "internal_error",
        f"Внутренняя ошибка: {service_title(current_service())}. "
        f"Сообщите в поддержку код запроса {request_id}",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(OperationalError, database_error_handler)
    app.add_exception_handler(DBAPIError, database_error_handler)
    # Прочие исключения ловит RequestContextMiddleware (observability.setup_app).
