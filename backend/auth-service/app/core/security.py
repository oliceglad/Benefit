"""Хэширование паролей и одноразовых секретов."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_password_hasher = PasswordHasher()
# Хэш для сравнения, когда пользователь не найден: время ответа на логин
# не должно выдавать, существует ли аккаунт.
_DUMMY_HASH = _password_hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _password_hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def generate_verification_code(length: int = 6) -> str:
    return f"{secrets.randbelow(10**length):0{length}d}"


def hash_verification_code(code: str) -> str:
    """HMAC с серверным секретом: короткий код нельзя перебрать по хэшу из БД."""
    return hmac.new(
        settings.secret_key.encode(), code.encode(), hashlib.sha256
    ).hexdigest()


def generate_token() -> str:
    """Случайный токен с высокой энтропией (refresh, state, коды входа)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
