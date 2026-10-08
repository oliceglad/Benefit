from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient

from app.core.jwt import decode_access_token
from app.main import app
from app.services.oidc import (
    OIDCProviderConfig,
    ProviderRegistry,
    get_provider_registry,
)
from tests.conftest import FakeMailClient
from tests.test_auth import register_and_verify

API = "/api/v1"


class FakeProvider:
    """Провайдер, который «логинит» заранее заданного пользователя."""

    def __init__(self, claims: dict[str, Any]) -> None:
        self.config = OIDCProviderConfig(
            id="fsp_id",
            name="ФСП ID",
            issuer="https://idp",
            client_id="c",
            client_secret="s",
        )
        self.claims = claims
        self.nonce: str | None = None

    @property
    def id(self) -> str:
        return self.config.id

    async def authorization_url(
        self, *, redirect_uri: str, state: str, nonce: str, code_verifier: str
    ) -> str:
        self.nonce = nonce
        return f"https://idp/auth?state={state}"

    async def exchange_code(self, **_: str) -> dict[str, Any]:
        return {"id_token": "token"}

    async def verify_id_token(self, id_token: str, *, nonce: str) -> dict[str, Any]:
        assert nonce == self.nonce
        return self.claims


@pytest.fixture
def provider() -> Iterator[FakeProvider]:
    fake = FakeProvider(
        {
            "sub": "fsp-1",
            "email": "ivanov@fsp-test.ru",
            "email_verified": True,
            "name": "Иванов Иван",
        }
    )
    app.dependency_overrides[get_provider_registry] = lambda: ProviderRegistry([fake])
    yield fake
    app.dependency_overrides.pop(get_provider_registry, None)


async def login_via_provider(
    client: AsyncClient, role: str | None = None
) -> dict[str, list[str]]:
    params = {"role": role} if role else {}
    start = await client.get(f"{API}/auth/oauth/fsp_id/authorize", params=params)
    assert start.status_code == 302
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]

    callback = await client.get(
        f"{API}/auth/oauth/fsp_id/callback", params={"code": "c", "state": state}
    )
    assert callback.status_code == 302
    return parse_qs(urlparse(callback.headers["location"]).query)


async def test_providers_list(client: AsyncClient, provider: FakeProvider) -> None:
    response = await client.get(f"{API}/auth/providers")
    assert response.json() == [{"id": "fsp_id", "name": "ФСП ID"}]


async def test_new_user_via_provider(
    client: AsyncClient, provider: FakeProvider
) -> None:
    query = await login_via_provider(client, role="candidate")

    tokens = await client.post(
        f"{API}/auth/oauth/exchange", json={"code": query["code"][0]}
    )
    assert tokens.status_code == 200
    claims = decode_access_token(tokens.json()["access_token"])
    assert claims["email"] == "ivanov@fsp-test.ru"
    assert claims["realm_access"]["roles"] == ["candidate"]

    # Код входа одноразовый.
    again = await client.post(
        f"{API}/auth/oauth/exchange", json={"code": query["code"][0]}
    )
    assert again.status_code == 400


async def test_repeat_login_finds_same_user(
    client: AsyncClient, provider: FakeProvider
) -> None:
    first = await login_via_provider(client, role="employer")
    second = await login_via_provider(client)  # роль уже не нужна

    sub = set()
    for query in (first, second):
        tokens = await client.post(
            f"{API}/auth/oauth/exchange", json={"code": query["code"][0]}
        )
        claims = decode_access_token(tokens.json()["access_token"])
        assert claims["realm_access"]["roles"] == ["employer"]
        sub.add(claims["sub"])
    assert len(sub) == 1


async def test_new_user_without_role_gets_error(
    client: AsyncClient, provider: FakeProvider
) -> None:
    query = await login_via_provider(client)
    assert query["error"] == ["role_required"]


async def test_role_from_keycloak_claims(
    client: AsyncClient, provider: FakeProvider
) -> None:
    provider.claims["realm_access"] = {"roles": ["offline_access", "employer"]}

    query = await login_via_provider(client)

    tokens = await client.post(
        f"{API}/auth/oauth/exchange", json={"code": query["code"][0]}
    )
    claims = decode_access_token(tokens.json()["access_token"])
    assert claims["realm_access"]["roles"] == ["employer"]


async def test_links_existing_account_by_verified_email(
    client: AsyncClient, provider: FakeProvider, mail: FakeMailClient
) -> None:
    local = await register_and_verify(client, mail, "ivanov@fsp-test.ru", "employer")
    local_sub = decode_access_token(local["access_token"])["sub"]

    query = await login_via_provider(client, role="candidate")
    tokens = await client.post(
        f"{API}/auth/oauth/exchange", json={"code": query["code"][0]}
    )
    claims = decode_access_token(tokens.json()["access_token"])

    assert claims["sub"] == local_sub
    assert claims["realm_access"]["roles"] == ["employer"]


async def test_does_not_link_unverified_provider_email(
    client: AsyncClient, provider: FakeProvider, mail: FakeMailClient
) -> None:
    await register_and_verify(client, mail, "ivanov@fsp-test.ru")
    provider.claims["email_verified"] = False

    query = await login_via_provider(client, role="candidate")

    assert query["error"] == ["email_conflict"]


async def test_invalid_state(client: AsyncClient, provider: FakeProvider) -> None:
    callback = await client.get(
        f"{API}/auth/oauth/fsp_id/callback", params={"code": "c", "state": "forged"}
    )
    query = parse_qs(urlparse(callback.headers["location"]).query)
    assert query["error"] == ["invalid_state"]


async def test_provider_error_is_forwarded(
    client: AsyncClient, provider: FakeProvider
) -> None:
    callback = await client.get(
        f"{API}/auth/oauth/fsp_id/callback", params={"error": "access_denied"}
    )
    query = parse_qs(urlparse(callback.headers["location"]).query)
    assert query["error"] == ["access_denied"]


async def test_dev_callback_exchanges_code(
    client: AsyncClient, provider: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "app_env", "local")
    start = await client.get(
        f"{API}/auth/oauth/fsp_id/authorize", params={"role": "candidate"}
    )
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    callback = await client.get(
        f"{API}/auth/oauth/fsp_id/callback", params={"code": "c", "state": state}
    )
    location = urlparse(callback.headers["location"])
    assert location.path == f"{API}/auth/oauth-dev-callback"

    response = await client.get(f"{location.path}?{location.query}")

    assert response.status_code == 200
    assert "access_token" in response.json()


async def link_via_provider(
    client: AsyncClient, access_token: str
) -> dict[str, list[str]]:
    start = await client.post(
        f"{API}/auth/oauth/fsp_id/link",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert start.status_code == 200, start.text
    url = start.json()["authorization_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    callback = await client.get(
        f"{API}/auth/oauth/fsp_id/callback", params={"code": "c", "state": state}
    )
    return parse_qs(urlparse(callback.headers["location"]).query)


async def test_link_provider_to_existing_account(
    client: AsyncClient, provider: FakeProvider, mail: FakeMailClient
) -> None:
    # Почта в ФСП ID другая — автоматической привязки по почте не будет.
    tokens = await register_and_verify(client, mail, "dev@mail.ru")
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}

    query = await link_via_provider(client, tokens["access_token"])
    assert query == {"linked": ["fsp_id"]}

    identities = (await client.get(f"{API}/users/me/identities", headers=auth)).json()
    assert [i["provider"] for i in identities] == ["fsp_id"]

    # Теперь через ФСП ID входим в тот же аккаунт.
    login = await login_via_provider(client)
    exchanged = await client.post(
        f"{API}/auth/oauth/exchange", json={"code": login["code"][0]}
    )
    me = await client.get(
        f"{API}/users/me",
        headers={"Authorization": f"Bearer {exchanged.json()['access_token']}"},
    )
    assert me.json()["email"] == "dev@mail.ru"

    unlink = await client.delete(f"{API}/users/me/identities/fsp_id", headers=auth)
    assert unlink.status_code == 204


async def test_link_identity_taken_by_another_user(
    client: AsyncClient, provider: FakeProvider, mail: FakeMailClient
) -> None:
    await login_via_provider(client, role="candidate")  # создан другой пользователь
    tokens = await register_and_verify(client, mail, "dev@mail.ru")

    query = await link_via_provider(client, tokens["access_token"])

    assert query["error"] == ["identity_taken"]


async def test_cannot_unlink_last_login_method(
    client: AsyncClient, provider: FakeProvider
) -> None:
    query = await login_via_provider(client, role="candidate")
    tokens = await client.post(
        f"{API}/auth/oauth/exchange", json={"code": query["code"][0]}
    )

    response = await client.delete(
        f"{API}/users/me/identities/fsp_id",
        headers={"Authorization": f"Bearer {tokens.json()['access_token']}"},
    )

    assert response.status_code == 409


async def test_internal_identities_requires_token(
    client: AsyncClient, provider: FakeProvider
) -> None:
    from app.core.config import settings
    from app.core.jwt import decode_access_token as decode

    query = await login_via_provider(client, role="candidate")
    tokens = await client.post(
        f"{API}/auth/oauth/exchange", json={"code": query["code"][0]}
    )
    user_id = decode(tokens.json()["access_token"])["sub"]
    url = f"/internal/v1/users/{user_id}/identities"

    assert (await client.get(url)).status_code == 401
    response = await client.get(
        url, headers={"X-Internal-Token": settings.internal_api_token}
    )
    assert response.status_code == 200
    assert response.json()[0]["subject"] == "fsp-1"
