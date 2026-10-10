"""Метрики Prometheus: HTTP-запросы, ошибки API, межсервисные вызовы, outbox.

Метрики собираются в процессе сервиса и отдаются на ``GET /metrics``
(только во внутренней сети — шлюз этот путь не проксирует). Имя сервиса
метки не содержат: Prometheus добавляет его из конфигурации сбора (``job``).
"""

import time

from fastapi import FastAPI, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.types import ASGIApp, Message, Receive, Scope, Send

LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30)

HTTP_REQUESTS = Counter(
    "benefit_http_requests_total",
    "HTTP-запросы к API",
    ["method", "route", "status"],
)
HTTP_DURATION = Histogram(
    "benefit_http_request_duration_seconds",
    "Время обработки HTTP-запроса",
    ["method", "route"],
    buckets=LATENCY_BUCKETS,
)
HTTP_IN_PROGRESS = Gauge(
    "benefit_http_requests_in_progress", "Запросы в обработке прямо сейчас"
)
APP_ERRORS = Counter(
    "benefit_app_errors_total",
    "Ответы с ошибкой по коду (invalid_credentials, upstream_unavailable, …)",
    ["code", "status"],
)
UPSTREAM_REQUESTS = Counter(
    "benefit_upstream_requests_total",
    "Вызовы внутреннего API других сервисов",
    ["target", "outcome"],
)
UPSTREAM_DURATION = Histogram(
    "benefit_upstream_request_duration_seconds",
    "Время вызова другого сервиса",
    ["target"],
    buckets=LATENCY_BUCKETS,
)
OUTBOX_DELIVERED = Counter(
    "benefit_outbox_delivered_total", "Доставленные сообщения outbox", ["kind"]
)
OUTBOX_RETRIES = Counter(
    "benefit_outbox_retries_total",
    "Неудачные попытки доставки (будут повторены)",
    ["kind"],
)
OUTBOX_FAILED = Counter(
    "benefit_outbox_failed_total",
    "Сообщения, доставка которых прекращена (нужен разбор)",
    ["kind"],
)
OUTBOX_PENDING = Gauge(
    "benefit_outbox_pending", "Сообщения outbox в очереди", ["table"]
)
OUTBOX_OLDEST_SECONDS = Gauge(
    "benefit_outbox_oldest_pending_seconds",
    "Возраст самого старого недоставленного сообщения",
    ["table"],
)

# Критичные ошибки создаются с нулём при старте: ``increase()`` не видит
# первое появление счётчика, и первый же сбой почты или базы иначе не
# вызвал бы алерт.
for _code, _status in (
    ("database_unavailable", 503),
    ("internal_error", 500),
    ("mail_unavailable", 503),
    ("registry_unavailable", 503),
    ("upstream_unavailable", 503),
):
    APP_ERRORS.labels(_code, str(_status))

# Пути, которые не учитываются в метриках запросов.
SKIPPED_PATHS = {"/metrics"}


class MetricsMiddleware:
    """Считает запросы по шаблону маршрута (``/vacancies/{vacancy_id}``),
    а не по фактическому пути — иначе метрик было бы по одной на каждый id."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in SKIPPED_PATHS:
            await self.app(scope, receive, send)
            return
        status = 500
        started = time.perf_counter()

        async def send_with_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        HTTP_IN_PROGRESS.inc()
        try:
            await self.app(scope, receive, send_with_status)
        finally:
            HTTP_IN_PROGRESS.dec()
            template = route_template(scope)
            method = scope["method"]
            HTTP_REQUESTS.labels(method, template, str(status)).inc()
            HTTP_DURATION.labels(method, template).observe(
                time.perf_counter() - started
            )


def route_template(scope: Scope) -> str:
    """Полный шаблон маршрута: ``/api/v1/employers/vacancies/{vacancy_id}``.

    У маршрута подключённого роутера путь относительный, поэтому префикс
    восстанавливается из фактического пути (префиксы без параметров).
    """
    route = scope.get("route")
    path = getattr(route, "path", None)
    if path is None:
        return "unmatched"
    try:
        rendered = route.path_format.format(**(scope.get("path_params") or {}))
    except (AttributeError, KeyError, IndexError, ValueError):
        return path
    actual = scope["path"]
    if rendered and actual.endswith(rendered):
        return actual[: len(actual) - len(rendered)] + path
    return path


def record_error(code: str, status: int) -> None:
    APP_ERRORS.labels(code, str(status)).inc()


def setup_metrics(app: FastAPI) -> None:
    app.add_middleware(MetricsMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
