import pytest
from httpx import AsyncClient

from app.core.jwt import decode_access_token
from tests.conftest import FakeMailClient

API = "/api/v1"
PASSWORD = "secret123"


async def register(
    client: AsyncClient, email: str = "user@mail.ru", role: str = "candidate"
) -> dict:
    response = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": PASSWORD, "role": role},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def register_and_verify(
    client: AsyncClient, mail: FakeMailClient, email: str, role: str = "candidate"
) -> dict:
    await register(client, email, role)
    response = await client.post(
        f"{API}/auth/verify-email", json={"email": email, "code": mail.codes[email]}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_health(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/health")).json() == {"status": "ok"}
    assert (await client.get(f"{API}/health/db")).json() == {"status": "ok"}


@pytest.mark.parametrize(
    "email",
    ["user@gmail.com", "user@yandex.com", "user@mail.ru.evil.com"],
)
async def test_register_rejects_non_russian_domains(
    client: AsyncClient, email: str
) -> None:
    response = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": PASSWORD, "role": "candidate"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "email_domain_not_allowed"


@pytest.mark.parametrize(
    "email", ["user@yandex.ru", "user@company.su", "user@почта.рф", "User@Mail.RU"]
)
async def test_register_accepts_russian_domains(
    client: AsyncClient, mail: FakeMailClient, email: str
) -> None:
    body = await register(client, email)

    assert body["email"] == email.lower()
    assert email.lower() in mail.codes


async def test_register_rejects_weak_password(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/auth/register",
        json={"email": "user@mail.ru", "password": "onlyletters", "role": "employer"},
    )
    assert response.status_code == 422


async def test_full_email_flow(client: AsyncClient, mail: FakeMailClient) -> None:
    await register(client, role="employer")

    login = await client.post(
        f"{API}/auth/login", json={"email": "user@mail.ru", "password": PASSWORD}
    )
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "email_not_verified"

    tokens = await client.post(
        f"{API}/auth/verify-email",
        json={"email": "user@mail.ru", "code": mail.codes["user@mail.ru"]},
    )
    assert tokens.status_code == 200
    claims = decode_access_token(tokens.json()["access_token"])
    assert claims["realm_access"]["roles"] == ["employer"]
    assert claims["email_verified"] is True

    login = await client.post(
        f"{API}/auth/login", json={"email": "USER@mail.ru", "password": PASSWORD}
    )
    assert login.status_code == 200

    me = await client.get(
        f"{API}/users/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["role"] == "employer"
    assert me.json()["is_email_verified"] is True


async def test_wrong_code_counts_attempts(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    await register(client)
    wrong = "000000" if mail.codes["user@mail.ru"] != "000000" else "111111"

    for _ in range(5):
        response = await client.post(
            f"{API}/auth/verify-email", json={"email": "user@mail.ru", "code": wrong}
        )
        assert response.json()["error"]["code"] == "invalid_code"

    response = await client.post(
        f"{API}/auth/verify-email",
        json={"email": "user@mail.ru", "code": mail.codes["user@mail.ru"]},
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "too_many_attempts"


async def test_resend_code_has_cooldown(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    await register(client)

    response = await client.post(
        f"{API}/auth/resend-code", json={"email": "user@mail.ru"}
    )

    assert response.status_code == 429
    assert "Retry-After" in response.headers


async def test_resend_for_unknown_email_is_silent(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/auth/resend-code", json={"email": "nobody@mail.ru"}
    )
    assert response.status_code == 202


async def test_register_twice_after_verification_conflicts(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    await register_and_verify(client, mail, "user@mail.ru")

    response = await client.post(
        f"{API}/auth/register",
        json={"email": "user@mail.ru", "password": PASSWORD, "role": "candidate"},
    )
    assert response.status_code == 409


async def test_mail_failure_returns_503_and_allows_retry(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    mail.fail = True
    response = await client.post(
        f"{API}/auth/register",
        json={"email": "user@mail.ru", "password": PASSWORD, "role": "candidate"},
    )
    assert response.status_code == 503

    mail.fail = False
    await register(client)
    assert "user@mail.ru" in mail.codes


async def test_login_with_wrong_password(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    await register_and_verify(client, mail, "user@mail.ru")

    response = await client.post(
        f"{API}/auth/login", json={"email": "user@mail.ru", "password": "wrong123"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_refresh_rotation_and_reuse_detection(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    tokens = await register_and_verify(client, mail, "user@mail.ru")
    first_refresh = tokens["refresh_token"]

    rotated = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": first_refresh}
    )
    assert rotated.status_code == 200
    second_refresh = rotated.json()["refresh_token"]

    # Повторное использование старого токена отзывает все сессии.
    reused = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": first_refresh}
    )
    assert reused.status_code == 401
    revoked = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": second_refresh}
    )
    assert revoked.status_code == 401


async def test_logout_revokes_refresh_token(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    tokens = await register_and_verify(client, mail, "user@mail.ru")

    logout = await client.post(
        f"{API}/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout.status_code == 204
    refresh = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401


async def test_me_requires_token(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/users/me")).status_code == 401
    response = await client.get(
        f"{API}/users/me", headers={"Authorization": "Bearer garbage"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


async def test_jwks_verifies_issued_tokens(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    import jwt

    tokens = await register_and_verify(client, mail, "user@mail.ru")
    jwks = (await client.get("/.well-known/jwks.json")).json()

    header = jwt.get_unverified_header(tokens["access_token"])
    [key] = [k for k in jwks["keys"] if k["kid"] == header["kid"]]
    claims = jwt.decode(
        tokens["access_token"],
        jwt.PyJWK(key),
        algorithms=["RS256"],
        audience="benefit",
    )
    assert claims["realm_access"]["roles"] == ["candidate"]


async def test_admin_role_cannot_be_self_assigned(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/auth/register",
        json={"email": "boss@mail.ru", "password": PASSWORD, "role": "admin"},
    )
    assert response.status_code == 422


async def test_admin_token_has_admin_role(client: AsyncClient) -> None:
    from datetime import UTC, datetime

    from app.core.security import hash_password
    from app.db.session import async_session_factory
    from app.models.user import User, UserRole

    async with async_session_factory() as session:
        session.add(
            User(
                email="admin@benefit.ru",
                password_hash=hash_password(PASSWORD),
                role=UserRole.ADMIN,
                email_verified_at=datetime.now(UTC),
            )
        )
        await session.commit()

    response = await client.post(
        f"{API}/auth/login", json={"email": "admin@benefit.ru", "password": PASSWORD}
    )

    claims = decode_access_token(response.json()["access_token"])
    assert claims["realm_access"]["roles"] == ["admin"]
