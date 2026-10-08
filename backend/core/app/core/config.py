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

    # Сервисы для страницы состояния: имя -> адрес health-эндпоинта
    # во внутренней сети.
    status_services: dict[str, str] = {
        "auth-service": "http://auth-service:8000/api/v1/health",
        "candidate-service": "http://candidate-service:8000/api/v1/candidates/health",
        "assessment-service": "http://assessment-service:8000/api/v1/assessments/health",
        "applications-service": "http://applications-service:8000/api/v1/invitations/health",
        "notification-service": "http://notification-service:8000/api/v1/notifications/health",
        "chat-service": "http://chat-service:8000/api/v1/chat/health",
        "employer-service": "http://employer-service:8000/api/v1/employers/health",
        "matching-service": "http://matching-service:8000/api/v1/talent/health",
        "mail-service": "http://mail-service:8000/api/v1/health",
    }

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
