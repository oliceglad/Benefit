"""Конфигурация candidate-service."""

from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Benefit Candidates"
    app_env: Literal["local", "test", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api/v1/candidates"

    postgres_host: str = "localhost"
    postgres_port: int = 5434
    postgres_db: str = "candidates"
    postgres_user: str = "candidates"
    postgres_password: str = "candidates"

    # Межсервисное взаимодействие (токен и проверку JWT настраивает
    # benefit_common.settings).
    auth_internal_url: str = "http://localhost:8001"

    # API достижений ФСП (пока — mock), доступ по учётным данным клиента.
    fsp_api_url: str = "http://localhost:8003"
    fsp_client_id: str = "benefit"
    fsp_client_secret: str = "fsp-dev-secret"
    fsp_provider_id: str = "fsp_id"

    # Версии текстов согласий. Смена версии требует повторного согласия.
    consent_personal_data_version: str = "2026-10-01"
    consent_publication_version: str = "2026-10-01"
    consent_personal_data_url: str = "/legal/personal-data"
    consent_publication_url: str = "/legal/publication"

    photo_max_bytes: int = 5 * 1024 * 1024
    photo_max_side: int = 800
    resume_import_max_bytes: int = 10 * 1024 * 1024

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
