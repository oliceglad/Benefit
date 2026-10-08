"""Хелперы для тестов сервисов: токены, подписанные тестовым ключом."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from benefit_common.security import jwks_cache
from benefit_common.settings import get_common_settings

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = "test-key"


def install_test_jwks() -> None:
    """Подменяет JWKS auth-service тестовым ключом (без сетевых запросов)."""
    jwk = RSAAlgorithm.to_jwk(_KEY.public_key(), as_dict=True)
    jwks_cache._keys = {_KID: jwt.PyJWK({**jwk, "kid": _KID, "alg": "RS256"})}
    jwks_cache._loaded_at = float("inf")


def make_token(
    user_id: uuid.UUID, role: str, email: str = "user@mail.ru", **claims: object
) -> str:
    settings = get_common_settings()
    now = datetime.now(UTC)
    payload = {
        "iss": settings.auth_issuer,
        "aud": settings.auth_audience,
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "email": email,
        "realm_access": {"roles": [role]},
        **claims,
    }
    return jwt.encode(payload, _KEY, algorithm="RS256", headers={"kid": _KID})


class TestUser:
    """Пользователь с готовыми заголовками авторизации."""

    __test__ = False  # не тестовый класс для pytest

    def __init__(self, role: str, email: str = "user@mail.ru") -> None:
        self.id = uuid.uuid4()
        self.role = role
        self.email = email
        self.headers = {"Authorization": f"Bearer {make_token(self.id, role, email)}"}


async def ensure_database(
    *, host: str, port: int, user: str, password: str, database: str
) -> None:
    """Создаёт тестовую базу, если её ещё нет (нужен пакет asyncpg)."""
    import asyncpg

    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database="postgres"
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", database
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{database}"')
    finally:
        await conn.close()
