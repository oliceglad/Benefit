"""Настройки, общие для всех сервисов (читаются из окружения)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Проверка access-токенов auth-service (формат совместим с Keycloak).
    auth_jwks_url: str = "http://localhost:8000/.well-known/jwks.json"
    auth_issuer: str = "http://localhost:8000"
    auth_audience: str = "benefit"

    # Токен для вызовов внутреннего API между сервисами.
    internal_api_token: str = "change-me"


@lru_cache
def get_common_settings() -> CommonSettings:
    return CommonSettings()
