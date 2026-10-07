"""Конфигурация приложения, загружаемая из переменных окружения."""

from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Настройки приложения.

    Значения берутся из переменных окружения или файла ``.env``
    (сначала корень репозитория, затем папка ``backend``).
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Benefit"
    app_env: Literal["local", "test", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = []

    # Проверка access-токенов auth-service (совместимы с Keycloak).
    auth_jwks_url: str = "http://localhost:8000/.well-known/jwks.json"
    auth_issuer: str = "http://localhost:8000"
    auth_audience: str = "benefit"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "benefit"
    postgres_user: str = "benefit"
    postgres_password: str = "benefit"

    @computed_field
    @property
    def database_url(self) -> URL:
        """URL подключения к PostgreSQL через асинхронный драйвер asyncpg."""
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    """Возвращает закэшированный экземпляр настроек."""
    return Settings()


settings = get_settings()
