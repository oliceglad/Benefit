from datetime import UTC, datetime, timedelta
from typing import Annotated

import pytest
from benefit_common.testing import TestUser, install_test_jwks, make_token
from fastapi import APIRouter, Depends
from httpx import AsyncClient

from app.api.deps import Principal, Role, require_roles
from app.main import app

_router = APIRouter()


@_router.get("/_test/employer-only")
async def employer_only(
    user: Annotated[Principal, Depends(require_roles(Role.EMPLOYER))],
) -> dict[str, str]:
    return {"email": user.email}


@_router.post("/_test/employer-only")
async def employer_action(
    user: Annotated[Principal, Depends(require_roles(Role.EMPLOYER))],
) -> dict[str, str]:
    return {"email": user.email}


app.include_router(_router)


@pytest.fixture(autouse=True)
def jwks() -> None:
    install_test_jwks()


async def test_employer_allowed(client: AsyncClient) -> None:
    user = TestUser("employer")
    response = await client.get("/_test/employer-only", headers=user.headers)
    assert response.status_code == 200


async def test_candidate_forbidden(client: AsyncClient) -> None:
    user = TestUser("candidate")
    response = await client.get("/_test/employer-only", headers=user.headers)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "token",
    [
        None,
        "garbage",
        make_token(TestUser("employer").id, "employer", iss="https://evil"),
        make_token(
            TestUser("employer").id,
            "employer",
            exp=datetime.now(UTC) - timedelta(minutes=1),
        ),
    ],
)
async def test_invalid_tokens_rejected(client: AsyncClient, token: str | None) -> None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = await client.get("/_test/employer-only", headers=headers)
    assert response.status_code == 401


async def test_cookie_auth_and_csrf() -> None:
    from httpx import ASGITransport

    user = TestUser("employer")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=user.cookies()
    ) as client:
        assert (await client.get("/_test/employer-only")).status_code == 200
        # Изменяющий запрос по cookie без CSRF-заголовка отклоняется.
        assert (await client.post("/_test/employer-only")).status_code == 403
        wrong = await client.post(
            "/_test/employer-only", headers={"X-CSRF-Token": "other"}
        )
        assert wrong.status_code == 403
        ok = await client.post(
            "/_test/employer-only", headers={"X-CSRF-Token": "test-csrf"}
        )
        assert ok.status_code == 200


async def test_bearer_header_needs_no_csrf(client: AsyncClient) -> None:
    user = TestUser("employer")
    response = await client.post("/_test/employer-only", headers=user.headers)
    assert response.status_code == 200
