import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Depends
from httpx import AsyncClient
from jwt.algorithms import RSAAlgorithm

from app.api.deps import require_roles
from app.core.config import settings
from app.core.security import Principal, Role, jwks_cache
from app.main import app

_router = APIRouter()


@_router.get("/_test/employer-only")
async def employer_only(
    user: Annotated[Principal, Depends(require_roles(Role.EMPLOYER))],
) -> dict[str, str]:
    return {"email": user.email}


app.include_router(_router)

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KID = "test-key"


@pytest.fixture(autouse=True)
def fake_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    async def load() -> None:
        jwk = RSAAlgorithm.to_jwk(KEY.public_key(), as_dict=True)
        jwks_cache._keys = {KID: jwt.PyJWK({**jwk, "kid": KID, "alg": "RS256"})}
        jwks_cache._loaded_at = float("inf")

    monkeypatch.setattr(jwks_cache, "_load", load)


def make_token(roles: list[str], **overrides: object) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": settings.auth_issuer,
        "aud": settings.auth_audience,
        "sub": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "email": "user@mail.ru",
        "realm_access": {"roles": roles},
        **overrides,
    }
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": KID})


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_employer_allowed(client: AsyncClient) -> None:
    response = await client.get(
        "/_test/employer-only", headers=auth(make_token(["employer"]))
    )
    assert response.status_code == 200


async def test_candidate_forbidden(client: AsyncClient) -> None:
    response = await client.get(
        "/_test/employer-only", headers=auth(make_token(["candidate"]))
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "token",
    [
        None,
        "garbage",
        make_token(["employer"], iss="https://evil"),
        make_token(["employer"], exp=datetime.now(UTC) - timedelta(minutes=1)),
    ],
)
async def test_invalid_tokens_rejected(client: AsyncClient, token: str | None) -> None:
    headers = auth(token) if token else {}
    response = await client.get("/_test/employer-only", headers=headers)
    assert response.status_code == 401
