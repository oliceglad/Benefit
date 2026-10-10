from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models import OutboxMessage, User
from app.services.deletion import build_relay, targets
from tests.conftest import FakeMailClient
from tests.test_auth import PASSWORD, register, register_and_verify

API = "/api/v1"
NEW_PASSWORD = "brandnew456"


def bearer(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def login(client: AsyncClient, email: str, password: str) -> Any:
    return await client.post(
        f"{API}/auth/login", json={"email": email, "password": password}
    )


# --- Восстановление пароля ---------------------------------------------------------


async def test_reset_password_by_email_code(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    tokens = await register_and_verify(client, mail, "user@mail.ru")

    response = await client.post(
        f"{API}/auth/password/forgot", json={"email": "user@mail.ru"}
    )
    assert response.status_code == 202
    assert mail.purposes["user@mail.ru"] == "reset_password"

    reset = await client.post(
        f"{API}/auth/password/reset",
        json={
            "email": "user@mail.ru",
            "code": mail.codes["user@mail.ru"],
            "new_password": NEW_PASSWORD,
        },
    )
    assert reset.status_code == 204, reset.text

    assert (await login(client, "user@mail.ru", PASSWORD)).status_code == 401
    assert (await login(client, "user@mail.ru", NEW_PASSWORD)).status_code == 200
    # Старые сессии завершены.
    refresh = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401
    assert mail.notifications[-1][1] == "Benefit: пароль изменён"
    # Код одноразовый.
    again = await client.post(
        f"{API}/auth/password/reset",
        json={
            "email": "user@mail.ru",
            "code": mail.codes["user@mail.ru"],
            "new_password": "another789",
        },
    )
    assert again.json()["error"]["code"] == "invalid_code"


async def test_forgot_password_does_not_reveal_accounts(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    await register_and_verify(client, mail, "user@mail.ru")
    unknown = await client.post(
        f"{API}/auth/password/forgot", json={"email": "nobody@mail.ru"}
    )
    first = await client.post(
        f"{API}/auth/password/forgot", json={"email": "user@mail.ru"}
    )
    code = mail.codes["user@mail.ru"]
    # Повтор раньше времени не выдаёт ошибку (иначе было бы видно, что
    # аккаунт есть) и не меняет код.
    repeat = await client.post(
        f"{API}/auth/password/forgot", json={"email": "user@mail.ru"}
    )

    assert unknown.status_code == first.status_code == repeat.status_code == 202
    assert "nobody@mail.ru" not in mail.codes
    assert mail.codes["user@mail.ru"] == code


async def test_reset_code_attempts_are_limited(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    await register_and_verify(client, mail, "user@mail.ru")
    await client.post(f"{API}/auth/password/forgot", json={"email": "user@mail.ru"})
    code = mail.codes["user@mail.ru"]
    wrong = "000000" if code != "000000" else "111111"

    body = {"email": "user@mail.ru", "code": wrong, "new_password": NEW_PASSWORD}
    for _ in range(5):
        await client.post(f"{API}/auth/password/reset", json=body)
    response = await client.post(
        f"{API}/auth/password/reset", json={**body, "code": code}
    )

    assert response.json()["error"]["code"] == "too_many_attempts"


async def test_reset_takes_over_unverified_registration(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    """Владелец почты, на которую кто-то зарегистрировался, задаёт свой
    пароль через восстановление — пароль регистрации больше не работает."""
    await register(client, "victim@mail.ru")
    await client.post(f"{API}/auth/password/forgot", json={"email": "victim@mail.ru"})
    await client.post(
        f"{API}/auth/password/reset",
        json={
            "email": "victim@mail.ru",
            "code": mail.codes["victim@mail.ru"],
            "new_password": NEW_PASSWORD,
        },
    )

    assert (await login(client, "victim@mail.ru", PASSWORD)).status_code == 401
    assert (await login(client, "victim@mail.ru", NEW_PASSWORD)).status_code == 200


# --- Смена пароля и профиль ----------------------------------------------------------


async def test_change_password(client: AsyncClient, mail: FakeMailClient) -> None:
    tokens = await register_and_verify(client, mail, "user@mail.ru")

    wrong = await client.post(
        f"{API}/users/me/password",
        json={"current_password": "nope12345", "new_password": NEW_PASSWORD},
        headers=bearer(tokens),
    )
    assert wrong.json()["error"]["code"] == "invalid_password"
    weak = await client.post(
        f"{API}/users/me/password",
        json={"current_password": PASSWORD, "new_password": "onlyletters"},
        headers=bearer(tokens),
    )
    assert weak.status_code == 422

    response = await client.post(
        f"{API}/users/me/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=bearer(tokens),
    )
    assert response.status_code == 200, response.text
    fresh = response.json()

    # Старая сессия завершена, новая работает.
    old = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert old.status_code == 401
    new = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": fresh["refresh_token"]}
    )
    assert new.status_code == 200
    assert (await login(client, "user@mail.ru", NEW_PASSWORD)).status_code == 200


async def test_update_profile(client: AsyncClient, mail: FakeMailClient) -> None:
    tokens = await register_and_verify(client, mail, "user@mail.ru")

    response = await client.patch(
        f"{API}/users/me", json={"full_name": "  Иванова Анна "}, headers=bearer(tokens)
    )

    assert response.json()["full_name"] == "Иванова Анна"
    assert response.json()["has_password"] is True
    forbidden = await client.patch(
        f"{API}/users/me", json={"role": "admin"}, headers=bearer(tokens)
    )
    assert forbidden.status_code == 422


# --- Смена почты ---------------------------------------------------------------------


async def test_change_email(client: AsyncClient, mail: FakeMailClient) -> None:
    tokens = await register_and_verify(client, mail, "old@mail.ru")

    no_password = await client.post(
        f"{API}/users/me/email",
        json={"new_email": "new@mail.ru"},
        headers=bearer(tokens),
    )
    assert no_password.json()["error"]["code"] == "password_required"
    foreign = await client.post(
        f"{API}/users/me/email",
        json={"new_email": "new@gmail.com", "password": PASSWORD},
        headers=bearer(tokens),
    )
    assert foreign.json()["error"]["code"] == "email_domain_not_allowed"

    sent = await client.post(
        f"{API}/users/me/email",
        json={"new_email": "New@Mail.ru", "password": PASSWORD},
        headers=bearer(tokens),
    )
    assert sent.status_code == 202, sent.text
    assert mail.purposes["new@mail.ru"] == "change_email"
    # Пока код не введён, почта прежняя.
    me = await client.get(f"{API}/users/me", headers=bearer(tokens))
    assert me.json()["email"] == "old@mail.ru"

    confirmed = await client.post(
        f"{API}/users/me/email/confirm",
        json={"code": mail.codes["new@mail.ru"]},
        headers=bearer(tokens),
    )
    assert confirmed.status_code == 200, confirmed.text
    me = await client.get(f"{API}/users/me", headers=bearer(confirmed.json()))
    assert me.json()["email"] == "new@mail.ru"
    assert (await login(client, "new@mail.ru", PASSWORD)).status_code == 200
    assert (await login(client, "old@mail.ru", PASSWORD)).status_code == 401
    # Старый адрес предупреждён.
    assert mail.notifications[-1][0] == "old@mail.ru"


async def test_change_email_to_taken_address(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    tokens = await register_and_verify(client, mail, "first@mail.ru")
    await register_and_verify(client, mail, "second@mail.ru")

    response = await client.post(
        f"{API}/users/me/email",
        json={"new_email": "second@mail.ru", "password": PASSWORD},
        headers=bearer(tokens),
    )

    assert response.json()["error"]["code"] == "email_taken"


# --- Удаление ------------------------------------------------------------------------


async def outbox() -> list[OutboxMessage]:
    async with async_session_factory() as session:
        return list(await session.scalars(select(OutboxMessage)))


async def test_delete_account_with_password(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    tokens = await register_and_verify(client, mail, "user@mail.ru", "employer")
    user_id = (await client.get(f"{API}/users/me", headers=bearer(tokens))).json()["id"]

    wrong = await client.post(
        f"{API}/users/me/delete", json={"password": "nope12345"}, headers=bearer(tokens)
    )
    assert wrong.json()["error"]["code"] == "invalid_password"
    empty = await client.post(f"{API}/users/me/delete", json={}, headers=bearer(tokens))
    assert empty.json()["error"]["code"] == "confirmation_required"

    response = await client.post(
        f"{API}/users/me/delete", json={"password": PASSWORD}, headers=bearer(tokens)
    )

    assert response.status_code == 204
    assert (await login(client, "user@mail.ru", PASSWORD)).status_code == 401
    me = await client.get(f"{API}/users/me", headers=bearer(tokens))
    assert me.status_code == 401
    # Каждому сервису с данными пользователя — событие удаления.
    messages = await outbox()
    assert {m.kind for m in messages} == {f"user.deleted:{s}" for s in targets()}
    assert all(m.payload == {"user_id": user_id, "role": "employer"} for m in messages)
    # Почта освобождается: можно зарегистрироваться заново.
    assert (await register(client, "user@mail.ru"))["email"] == "user@mail.ru"


async def test_delete_account_with_email_code(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    tokens = await register_and_verify(client, mail, "user@mail.ru")

    sent = await client.post(f"{API}/users/me/delete-code", headers=bearer(tokens))
    assert sent.status_code == 202
    assert mail.purposes["user@mail.ru"] == "delete_account"
    response = await client.post(
        f"{API}/users/me/delete",
        json={"code": mail.codes["user@mail.ru"]},
        headers=bearer(tokens),
    )

    assert response.status_code == 204
    async with async_session_factory() as session:
        assert await session.scalar(select(User)) is None


async def test_deletion_is_delivered_to_services(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    tokens = await register_and_verify(client, mail, "user@mail.ru")
    await client.post(
        f"{API}/users/me/delete", json={"password": PASSWORD}, headers=bearer(tokens)
    )
    delivered: list[tuple[str, dict]] = []

    def handler(service: str) -> Any:
        async def deliver(payload: dict) -> None:
            delivered.append((service, payload))

        return deliver

    relay = build_relay(
        async_session_factory,
        {f"user.deleted:{s}": handler(s) for s in targets()},
    )
    await relay.process_batch()

    assert sorted(s for s, _ in delivered) == sorted(targets())
    assert all(m.sent_at is not None for m in await outbox())


async def test_cookie_session_gets_new_cookies_after_password_change(
    client: AsyncClient, mail: FakeMailClient
) -> None:
    await register_and_verify(client, mail, "user@mail.ru")
    login_response = await client.post(
        f"{API}/auth/login",
        json={"email": "user@mail.ru", "password": PASSWORD},
        headers={"X-Auth-Mode": "cookie"},
    )
    csrf = login_response.json()["csrf_token"]

    response = await client.post(
        f"{API}/users/me/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 200, response.text
    assert response.json()["delivery"] == "cookie"
    assert "benefit_access" in response.headers.get("set-cookie", "")
