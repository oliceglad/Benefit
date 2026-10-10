"""Конфигурация employer-service."""

from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Benefit Employers"
    app_env: Literal["local", "test", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    # Кабинет работодателя и публичный список вакансий.
    api_prefix: str = "/api/v1/employers"
    vacancies_prefix: str = "/api/v1/vacancies"

    postgres_host: str = "localhost"
    postgres_port: int = 5439
    postgres_db: str = "employers"
    postgres_user: str = "employers"
    postgres_password: str = "employers"

    matching_service_url: str = "http://localhost:8009"
    applications_service_url: str = "http://localhost:8005"

    # Проверка компаний по открытому реестру ФНС (ЕГРЮЛ/ЕГРИП).
    egrul_url: str = "https://egrul.nalog.ru"
    registry_timeout_seconds: float = 10.0
    # Проверенные компании периодически перепроверяются по реестру
    # (ликвидация снимает статус).
    verification_recheck_days: int = 30
    verification_recheck_enabled: bool = True

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
