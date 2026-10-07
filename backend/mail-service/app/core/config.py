"""Конфигурация mail-service."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Benefit Mail"
    app_env: Literal["local", "test", "production"] = "local"
    log_level: str = "INFO"

    # Токен, которым другие сервисы подписывают внутренние запросы.
    internal_api_token: str = "change-me"

    mail_from: str = "Benefit <no-reply@benefit.ru>"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    # SSL/TLS сразу при подключении (обычно порт 465).
    smtp_use_tls: bool = False
    # STARTTLS после подключения (обычно порт 587).
    smtp_start_tls: bool = False
    smtp_timeout_seconds: float = 10.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
