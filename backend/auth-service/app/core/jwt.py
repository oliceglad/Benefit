"""Выпуск и проверка access-токенов (JWT, RS256).

Публичная часть ключа отдаётся через JWKS, поэтому остальные сервисы
проверяют токены локально, без обращения к auth-service на каждый запрос.
"""

import base64
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.core.config import settings

logger = logging.getLogger(__name__)

ALGORITHM = "RS256"


def _load_or_create_private_key() -> rsa.RSAPrivateKey:
    if settings.jwt_private_key:
        pem = settings.jwt_private_key.replace("\\n", "\n").encode()
    else:
        path = settings.jwt_private_key_path
        if not path.exists():
            # В production отсутствие ключа ловит валидация настроек.
            logger.warning("JWT signing key not found, generating new one: %s", path)
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
            path.chmod(0o600)
        pem = path.read_bytes()

    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("JWT signing key must be an RSA private key")
    return key


def _jwk_thumbprint(jwk: dict[str, Any]) -> str:
    """RFC 7638: стабильный идентификатор ключа (kid)."""
    canonical = json.dumps(
        {k: jwk[k] for k in ("e", "kty", "n")}, separators=(",", ":"), sort_keys=True
    )
    digest = hashlib.sha256(canonical.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class JWTKeys:
    def __init__(self, private_key: rsa.RSAPrivateKey) -> None:
        self.private_key = private_key
        self.public_key = private_key.public_key()
        jwk = RSAAlgorithm.to_jwk(self.public_key, as_dict=True)
        self.kid = _jwk_thumbprint(jwk)
        self.public_jwk = {**jwk, "kid": self.kid, "use": "sig", "alg": ALGORITHM}


@lru_cache
def get_keys() -> JWTKeys:
    return JWTKeys(_load_or_create_private_key())


def jwks() -> dict[str, Any]:
    return {"keys": [get_keys().public_jwk]}


def create_access_token(
    *,
    subject: str,
    roles: list[str],
    email: str,
    email_verified: bool,
    name: str | None,
) -> tuple[str, int]:
    """Возвращает токен и его время жизни в секундах."""
    now = datetime.now(UTC)
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    claims: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "sub": subject,
        "aud": settings.jwt_audience,
        "azp": settings.jwt_audience,
        "iat": now,
        "exp": now + ttl,
        "jti": str(uuid.uuid4()),
        "typ": "Bearer",
        "email": email,
        "email_verified": email_verified,
        "preferred_username": email,
        "realm_access": {"roles": roles},
    }
    if name:
        claims["name"] = name
    keys = get_keys()
    token = jwt.encode(
        claims, keys.private_key, algorithm=ALGORITHM, headers={"kid": keys.kid}
    )
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    """Проверяет подпись, срок действия, issuer и audience.

    Raises:
        jwt.PyJWTError: токен невалиден.
    """
    return jwt.decode(
        token,
        get_keys().public_key,
        algorithms=[ALGORITHM],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "sub"]},
    )
