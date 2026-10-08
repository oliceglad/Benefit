"""Настройки, общие для всех сервисов (читаются из окружения)."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT = "change-me"


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test", "production"] = "local"

    # Проверка access-токенов auth-service (формат совместим с Keycloak).
    auth_jwks_url: str = "http://localhost:8000/.well-known/jwks.json"
    auth_issuer: str = "http://localhost:8000"
    auth_audience: str = "benefit"

    # Токен для вызовов внутреннего API между сервисами.
    internal_api_token: str = "change-me"

    # Токены в cookie (выставляет auth-service; имена должны совпадать).
    access_cookie_name: str = "benefit_access"
    csrf_cookie_name: str = "benefit_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    # Origin фронтенда: WebSocket с авторизацией по cookie принимается
    # только с этих адресов (защита от cross-site WebSocket hijacking).
    trusted_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    @model_validator(mode="after")
    def _check_production(self) -> Self:
        """В production сервис не стартует с небезопасной конфигурацией."""
        if self.app_env == "production":
            if (
                self.internal_api_token == INSECURE_DEFAULT
                or len(self.internal_api_token) < 32
            ):
                raise ValueError(
                    "INTERNAL_API_TOKEN: задайте случайный секрет (32+ символа)"
                )
            if any(o.startswith("http://") for o in self.trusted_origins):
                raise ValueError("TRUSTED_ORIGINS в production — только https://")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_common_settings() -> CommonSettings:
    return CommonSettings()
