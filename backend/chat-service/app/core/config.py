"""Конфигурация chat-service."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Benefit Chat"
    app_env: Literal["local", "test", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api/v1/chat"

    postgres_host: str = "localhost"
    postgres_port: int = 5438
    postgres_db: str = "chat"
    postgres_user: str = "chat"
    postgres_password: str = "chat"

    notification_service_url: str = "http://localhost:8006"
    candidate_service_url: str = "http://localhost:8004"

    # Вложения: локальный каталог (в docker — именованный том).
    files_dir: Path = Path("data/files")
    max_file_bytes: int = 20 * 1024 * 1024
    max_attachments_per_message: int = 10
    # Неприкреплённые к сообщению загрузки удаляются через столько часов.
    orphan_attachment_ttl_hours: int = 24
    # Неотправленных загрузок на пользователя (защита диска от переполнения).
    max_pending_attachments: int = 20

    message_max_length: int = 4000
    # Уведомление о новых сообщениях — не чаще раза в N минут на диалог.
    message_notification_window_minutes: int = 60

    # WebSocket: время на авторизацию после подключения и интервал пингов.
    ws_auth_timeout_seconds: float = 10.0
    ws_ping_interval_seconds: float = 25.0

    # Задания: напоминание за N часов до срока.
    task_reminder_hours: int = 24
    scheduler_interval_seconds: float = 30.0

    # Фоновые процессы (в тестах выключены и вызываются вручную).
    background_jobs_enabled: bool = True

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
