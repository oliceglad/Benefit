from httpx import AsyncClient

from tests.conftest import FakeMailClient
from tests.test_auth import PASSWORD, register

API = "/api/v1"
COOKIE_MODE = {"X-Auth-Mode": "cookie"}


async def verified(client: AsyncClient, mail: FakeMailClient) -> None:
    await register(client, "user@mail.ru")
    await client.post(
        f"{API}/auth/verify-email",
        json={"email": "user@mail.ru", "code": mail.codes["user@mail.ru"]},
    )
    client.cookies.clear()


async def cookie_login(client: AsyncClient) -> dict:
    response = await client.post(
        f"{API}/auth/login",
        json={"email": "user@mail.ru", "password": PASSWORD},
        headers=COOKIE_MODE,
    )
    assert response.status_code == 200, response.text
    return response


async def test_login_sets_httponly_cookies(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    await verified(client, mail)

    response = await cookie_login(client)

    body = response.json()
    assert (body["access_token"], body["refresh_token"]) == (None, None)
    assert body["delivery"] == "cookie"
    headers = {
        h.split("=", 1)[0]: h.lower() for h in response.headers.get_list("set-cookie")
    }
    assert "httponly" in headers["benefit_access"]
    assert "samesite=strict" in headers["benefit_access"]
    assert "path=/api/v1/auth" in headers["benefit_refresh"]
    assert "httponly" in headers["benefit_refresh"]
    # CSRF-cookie читается JS и совпадает с csrf_token в ответе.
    assert "httponly" not in headers["benefit_csrf"]
    assert client.cookies["benefit_csrf"] == body["csrf_token"]


async def test_body_mode_unchanged(client: AsyncClient, mail: FakeMailClient) -> None:
    await verified(client, mail)
    response = await client.post(
        f"{API}/auth/login", json={"email": "user@mail.ru", "password": PASSWORD}
    )
    assert response.json()["access_token"]
    assert response.json()["delivery"] == "body"
    assert not response.headers.get_list("set-cookie")


async def test_cookie_session_requests_and_csrf(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    await verified(client, mail)
    csrf = (await cookie_login(client)).json()["csrf_token"]

    me = await client.get(f"{API}/users/me")  # GET — без CSRF
    assert me.status_code == 200
    assert me.json()["email"] == "user@mail.ru"

    # Изменяющий запрос по cookie без CSRF-заголовка — отказ.
    link = await client.post(f"{API}/auth/oauth/fsp_id/link")
    assert link.json()["error"]["code"] == "csrf_failed"
    # С заголовком проверка CSRF проходит (дальше — нет провайдера в тестах).
    link = await client.post(
        f"{API}/auth/oauth/fsp_id/link", headers={"X-CSRF-Token": csrf}
    )
    assert link.json()["error"]["code"] != "csrf_failed"


async def test_refresh_and_logout_by_cookie(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    await verified(client, mail)
    csrf = (await cookie_login(client)).json()["csrf_token"]
    old_access = client.cookies["benefit_access"]

    no_csrf = await client.post(f"{API}/auth/refresh")
    assert no_csrf.status_code == 403

    refreshed = await client.post(f"{API}/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["delivery"] == "cookie"
    assert client.cookies["benefit_access"] != old_access
    new_csrf = refreshed.json()["csrf_token"]

    logout = await client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": new_csrf})
    assert logout.status_code == 204
    assert "benefit_access" not in client.cookies
    assert (await client.get(f"{API}/users/me")).status_code == 401
