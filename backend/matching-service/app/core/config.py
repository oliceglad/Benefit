"""Конфигурация matching-service."""

from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Benefit Matching"
    app_env: Literal["local", "test", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api/v1/talent"

    postgres_host: str = "localhost"
    postgres_port: int = 5440
    postgres_db: str = "matching"
    postgres_user: str = "matching"
    postgres_password: str = "matching"

    candidate_service_url: str = "http://localhost:8004"

    # Чтение ленты событий candidate-service.
    background_jobs_enabled: bool = True
    sync_interval_seconds: float = 2.0
    sync_batch_size: int = 200

    # Минимальная оценка, с которой кандидат попадает в подборку.
    match_min_score: int = 30

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
