"""Метрики Prometheus (benefit_common.metrics) на примере core."""

from httpx import AsyncClient


def metric(text: str, name: str, **labels: str) -> float:
    """Значение метрики с указанными метками (0, если её нет)."""
    wanted = [f'{k}="{v}"' for k, v in labels.items()]
    for line in text.splitlines():
        if line.startswith(name + "{") and all(w in line for w in wanted):
            return float(line.rsplit(" ", 1)[1])
    return 0.0


async def test_requests_are_counted_by_route_template(client: AsyncClient) -> None:
    before = (await client.get("/metrics")).text

    await client.get("/api/v1/health")
    await client.get("/api/v1/no-such-path")
    after = (await client.get("/metrics")).text

    route = {"method": "GET", "route": "/api/v1/health", "status": "200"}
    assert metric(after, "benefit_http_requests_total", **route) == (
        metric(before, "benefit_http_requests_total", **route) + 1
    )
    # Неизвестные пути не плодят метрики по каждому адресу.
    assert metric(after, "benefit_http_requests_total", route="unmatched") >= 1
    assert "/api/v1/no-such-path" not in after
    # Сам /metrics не учитывается.
    assert 'route="/metrics"' not in after


async def test_errors_are_counted_by_code(client: AsyncClient) -> None:
    before = (await client.get("/metrics")).text

    await client.get("/api/v1/no-such-path")
    after = (await client.get("/metrics")).text

    labels = {"code": "not_found", "status": "404"}
    assert metric(after, "benefit_app_errors_total", **labels) == (
        metric(before, "benefit_app_errors_total", **labels) + 1
    )
    # Критичные коды есть с нулём заранее — для алертов на первый же сбой.
    assert 'code="mail_unavailable"' in after
