"""Конфигурация сервиса, загружаемая из переменных окружения."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

INSECURE_DEFAULT = "change-me"


class Settings(BaseSettings):
    """Настройки auth-service.

    Значения берутся из переменных окружения или файла ``.env``
    в папке сервиса. В docker-compose переменные пробрасываются явно.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Benefit Auth"
    app_env: Literal["local", "test", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = []
    # Внешний адрес сервиса: из него строятся redirect_uri для OIDC.
    public_url: str = "http://localhost:8000"

    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_db: str = "auth"
    postgres_user: str = "auth"
    postgres_password: str = "auth"

    # Секрет для HMAC кодов подтверждения почты.
    secret_key: str = INSECURE_DEFAULT

    # JWT. Формат access-токена совместим с Keycloak (realm_access.roles),
    # чтобы сервисы-потребители одинаково проверяли наши токены и токены
    # Keycloak / ФСП ID.
    jwt_issuer: str = "http://localhost:8000"
    jwt_audience: str = "benefit"
    jwt_private_key: str | None = None
    jwt_private_key_path: Path = Path("keys/jwt_private.pem")
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # Регистрация по почте разрешена только для российских доменов.
    allowed_email_tlds: list[str] = ["ru", "su", "рф"]
    allowed_email_domains: list[str] = []
    password_min_length: int = 8

    verification_code_ttl_minutes: int = 10
    verification_code_max_attempts: int = 5
    verification_resend_cooldown_seconds: int = 60

    # Межсервисное взаимодействие.
    mail_service_url: str = "http://localhost:8002"
    internal_api_token: str = INSECURE_DEFAULT

    # OAuth / OIDC.
    oauth_state_ttl_minutes: int = 10
    oauth_login_code_ttl_seconds: int = 120
    # Куда вернуть браузер после входа через внешнего провайдера
    # (страница фронтенда). По умолчанию — отладочный эндпоинт сервиса.
    oauth_frontend_callback_url: str | None = None

    keycloak_enabled: bool = False
    keycloak_issuer: str = "http://localhost:8080/realms/benefit"
    # Адрес Keycloak внутри docker-сети, если он отличается от публичного.
    keycloak_internal_issuer: str | None = None
    keycloak_client_id: str = "benefit-auth"
    keycloak_client_secret: str = ""

    fsp_id_enabled: bool = False
    fsp_id_issuer: str = "http://localhost:8003/realms/fsp"
    fsp_id_internal_issuer: str | None = None
    fsp_id_client_id: str = "benefit"
    fsp_id_client_secret: str = ""

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

    @property
    def oauth_callback_redirect_url(self) -> str:
        return self.oauth_frontend_callback_url or (
            f"{self.public_url}{self.api_v1_prefix}/auth/oauth-dev-callback"
        )

    @model_validator(mode="after")
    def _check_production_secrets(self) -> Self:
        if self.app_env == "production":
            if INSECURE_DEFAULT in (self.secret_key, self.internal_api_token):
                raise ValueError(
                    "SECRET_KEY и INTERNAL_API_TOKEN обязательны в production"
                )
            if not self.jwt_private_key and not self.jwt_private_key_path.exists():
                raise ValueError("Ключ подписи JWT обязателен в production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Возвращает закэшированный экземпляр настроек."""
    return Settings()


settings = get_settings()
