"""Конфигурация applications-service."""

from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Benefit Applications"
    app_env: Literal["local", "test", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api/v1/invitations"
    applications_prefix: str = "/api/v1/applications"

    postgres_host: str = "localhost"
    postgres_port: int = 5437
    postgres_db: str = "applications"
    postgres_user: str = "applications"
    postgres_password: str = "applications"

    candidate_service_url: str = "http://localhost:8004"
    notification_service_url: str = "http://localhost:8006"
    chat_service_url: str = "http://localhost:8007"
    employer_service_url: str = "http://localhost:8008"

    # Срок, в течение которого кандидат может ответить на приглашение.
    invitation_ttl_days: int = 14

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
