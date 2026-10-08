"""Конфигурация assessment-service."""

from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Benefit Assessments"
    app_env: Literal["local", "test", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api/v1/assessments"

    postgres_host: str = "localhost"
    postgres_port: int = 5435
    postgres_db: str = "assessments"
    postgres_user: str = "assessments"
    postgres_password: str = "assessments"

    candidate_service_url: str = "http://localhost:8004"
    notification_service_url: str = "http://localhost:8006"
    chat_service_url: str = "http://localhost:8007"

    # Пороги результата (в процентах от максимального балла):
    # ниже pass — грейд не подтверждён; от pass — подтверждён целевой грейд;
    # от exceed — подтверждён грейд на ступень выше целевого.
    pass_percent: float = 75.0
    exceed_percent: float = 90.0

    # Повторная попытка в той же специализации — не раньше чем через
    # столько часов (ограничение частоты смены грейда).
    attempt_cooldown_hours: int = 168
    # Срок действия подтверждённого грейда.
    confirmation_valid_days: int = 365
    # Допуск на сетевые задержки при проверке лимитов времени.
    time_grace_seconds: int = 5

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
