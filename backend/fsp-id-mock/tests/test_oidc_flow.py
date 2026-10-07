import base64
import hashlib
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import MOCK_USERS, app, settings

OIDC = f"/realms/{settings.realm}/protocol/openid-connect"
REDIRECT_URI = settings.redirect_uris[0]
VERIFIER = "v" * 64
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest())
    .rstrip(b"=")
    .decode()
)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _form(user_id: str) -> dict[str, str]:
    return {
        "client_id": settings.client_id,
        "redirect_uri": REDIRECT_URI,
        "state": "st",
        "nonce": "nn",
        "code_challenge": CHALLENGE,
        "user_id": user_id,
    }


async def test_authorization_code_flow(client: AsyncClient) -> None:
    user = next(iter(MOCK_USERS.values()))
    page = await client.get(
        f"{OIDC}/auth",
        params={
            "client_id": settings.client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email",
            "state": "st",
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
        },
    )
    assert page.status_code == 200
    assert user.email in page.text

    redirect = await client.post(f"{OIDC}/auth", data=_form(user.sub))
    assert redirect.status_code == 302
    query = parse_qs(urlparse(redirect.headers["location"]).query)
    assert query["state"] == ["st"]

    response = await client.post(
        f"{OIDC}/token",
        data={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": REDIRECT_URI,
            "code_verifier": VERIFIER,
        },
        auth=(settings.client_id, settings.client_secret),
    )
    assert response.status_code == 200

    jwks = (await client.get(f"{OIDC}/certs")).json()
    claims = jwt.decode(
        response.json()["id_token"],
        jwt.PyJWK(jwks["keys"][0]),
        algorithms=["RS256"],
        audience=settings.client_id,
        issuer=settings.issuer,
    )
    assert claims["sub"] == user.sub
    assert claims["nonce"] == "nn"
    assert claims["email"] == user.email


async def test_rejects_wrong_pkce_verifier(client: AsyncClient) -> None:
    user = next(iter(MOCK_USERS.values()))
    redirect = await client.post(f"{OIDC}/auth", data=_form(user.sub))
    code = parse_qs(urlparse(redirect.headers["location"]).query)["code"][0]

    response = await client.post(
        f"{OIDC}/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": "wrong",
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


async def test_rejects_unknown_redirect_uri(client: AsyncClient) -> None:
    response = await client.get(
        f"{OIDC}/auth",
        params={
            "client_id": settings.client_id,
            "redirect_uri": "https://evil.example/cb",
            "scope": "openid",
        },
    )
    assert response.status_code == 400
