"""Внутреннее API между сервисами.

Внутренние эндпоинты (``/internal/*``) не публикуются через шлюз и
дополнительно требуют заголовок ``X-Internal-Token``.
"""

import hmac
import logging
from typing import Annotated, Any

import httpx
from fastapi import Header, HTTPException, status

from benefit_common.context import (
    REQUEST_ID_HEADER,
    current_request_id,
    service_title,
)
from benefit_common.errors import AppError, ServiceUnavailableError
from benefit_common.settings import get_common_settings

logger = logging.getLogger(__name__)

INTERNAL_TOKEN_HEADER = "X-Internal-Token"


def verify_internal_token(x_internal_token: Annotated[str, Header()] = "") -> None:
    """Зависимость для роутеров внутреннего API."""
    expected = get_common_settings().internal_api_token
    if not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


class InternalClient:
    """HTTP-клиент для внутреннего API другого сервиса.

    Сетевые ошибки и ответы 5xx превращаются в ``ServiceUnavailableError``
    (503), чтобы сбой соседнего сервиса не выглядел как ошибка 500.
    Ответы 4xx возвращаются вызывающему как есть.
    """

    def __init__(self, base_url: str, *, service: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        # Короткое имя («candidate») или полное («candidate-service»).
        self.service = service if service.endswith("-service") else f"{service}-service"
        self.timeout = timeout

    def _unavailable(self, reason: str) -> ServiceUnavailableError:
        return ServiceUnavailableError(
            f"{service_title(self.service).capitalize()} {reason}. "
            "Попробуйте повторить запрос позже",
            code="upstream_unavailable",
            service=self.service,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        headers = {INTERNAL_TOKEN_HEADER: get_common_settings().internal_api_token}
        request_id = current_request_id()
        if request_id:
            # Сквозной ID: запрос виден в логах всех сервисов цепочки.
            headers[REQUEST_ID_HEADER] = request_id
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    json=json,
                    params=params,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            logger.warning("%s %s%s timed out", method, self.service, path)
            raise self._unavailable("не ответил вовремя") from exc
        except httpx.HTTPError as exc:
            logger.warning("%s %s%s failed: %s", method, self.service, path, exc)
            raise self._unavailable("недоступен") from exc
        if response.status_code >= 500:
            logger.warning(
                "%s %s%s returned %s", method, self.service, path, response.status_code
            )
            raise self._unavailable("вернул внутреннюю ошибку")
        return response

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)


def raise_for_client_error(response: httpx.Response) -> None:
    """Пробрасывает ответ 4xx соседнего сервиса как прикладную ошибку."""
    if response.status_code < 400:
        return
    try:
        error = response.json().get("error") or {}
    except ValueError:
        error = {}
    raise AppError(
        error.get("message") or "Ошибка во внешнем сервисе",
        code=error.get("code") or "upstream_error",
        status_code=response.status_code,
        service=error.get("service"),
        details=error.get("details"),
    )
