"""Конфигурация notification-service."""

from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Benefit Notifications"
    app_env: Literal["local", "test", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api/v1/notifications"

    postgres_host: str = "localhost"
    postgres_port: int = 5436
    postgres_db: str = "notifications"
    postgres_user: str = "notifications"
    postgres_password: str = "notifications"

    auth_internal_url: str = "http://localhost:8001"
    mail_service_url: str = "http://localhost:8002"
    # Адрес фронтенда: из него строятся ссылки в письмах.
    frontend_url: str = "http://localhost:3000"

    # Фоновая отправка писем (в тестах выключена и вызывается вручную).
    outbox_relay_enabled: bool = True

    @computed_field
    @property
    def database_url(self) -> URL:
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
    return Settings()


settings = get_settings()
