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
