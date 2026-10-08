"""Единый формат ошибок (benefit_common) — на примере core."""

from typing import Annotated

import pytest
from benefit_common.errors import ServiceUnavailableError
from benefit_common.internal import InternalClient
from fastapi import APIRouter, Query
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from app.main import app

_router = APIRouter()


class Payload(BaseModel):
    name: str = Field(min_length=3)
    age: int = Field(ge=14)
    tags: list[str] = Field(max_length=2)


@_router.post("/_test/validate")
async def validate(data: Payload, limit: Annotated[int, Query(le=10)] = 5) -> dict:
    return {"ok": True}


@_router.get("/_test/crash")
async def crash() -> dict:
    raise RuntimeError("boom")


@_router.get("/_test/upstream")
async def upstream() -> dict:
    await InternalClient("http://127.0.0.1:9", service="auth", timeout=1).get("/x")
    return {}


app.include_router(_router)


async def test_not_found_is_readable(client: AsyncClient) -> None:
    response = await client.get("/api/v1/nope", headers={"X-Request-ID": "trace-12345"})

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["message"].startswith("Ресурс не найден")
    assert error["service"] == "core"
    assert error["request_id"] == "trace-12345"
    assert response.headers["x-request-id"] == "trace-12345"


async def test_validation_errors_in_russian(client: AsyncClient) -> None:
    response = await client.post(
        "/_test/validate?limit=50",
        json={"name": "Ян", "age": 10, "tags": ["a", "b", "c"], "extra": 1},
    )

    error = response.json()["error"]
    assert response.status_code == 422
    assert error["code"] == "validation_error"
    details = {d["field"]: d["message"] for d in error["details"]}
    assert details["name"] == "слишком короткое значение (минимум 3)"
    assert details["age"] == "значение должно быть не меньше 14"
    assert details["tags"] == "слишком много элементов (максимум 2)"
    assert details["limit"] == "значение должно быть не больше 10"
    assert error["message"] == "Проверьте данные: limit, name, age, tags"


async def test_unhandled_error_hides_details() -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_test/crash")

    error = response.json()["error"]
    assert response.status_code == 500
    assert error["code"] == "internal_error"
    assert "boom" not in error["message"]
    assert error["request_id"] in error["message"]
    assert response.headers["x-request-id"] == error["request_id"]


async def test_upstream_failure_names_the_service(client: AsyncClient) -> None:
    response = await client.get("/_test/upstream")

    error = response.json()["error"]
    assert response.status_code == 503
    assert error["code"] == "upstream_unavailable"
    assert error["service"] == "auth-service"
    assert error["message"].startswith("Сервис авторизации недоступен")


async def test_service_unavailable_error_keeps_origin() -> None:
    exc = ServiceUnavailableError("x", service="matching-service")
    assert exc.service == "matching-service"


@pytest.mark.parametrize("bad_id", ["short", "a" * 200, "with spaces and ;"])
async def test_unsafe_request_id_is_replaced(client: AsyncClient, bad_id: str) -> None:
    response = await client.get(
        "/api/v1/health", headers={"X-Request-ID": bad_id.replace("\n", "")}
    )
    assert response.headers["x-request-id"] != bad_id
