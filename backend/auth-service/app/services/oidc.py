"""Клиент внешних OpenID Connect провайдеров (Keycloak, ФСП ID).

Используется Authorization Code Flow + PKCE. ФСП ID построен на Keycloak,
поэтому оба провайдера работают через один и тот же клиент и отличаются
только конфигурацией.
"""

import base64
import hashlib
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import status

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

METADATA_TTL_SECONDS = 3600


class OIDCError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "provider_error"
    message = "Ошибка при обращении к провайдеру авторизации"


@dataclass(frozen=True)
class OIDCProviderConfig:
    id: str
    name: str
    # Публичный issuer: так его видит браузер и так он записан в токенах.
    issuer: str
    client_id: str
    client_secret: str
    # Адрес того же issuer внутри docker-сети (для запросов сервер-сервер).
    internal_issuer: str | None = None
    scopes: str = "openid email profile"


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class OIDCProvider:
    def __init__(self, config: OIDCProviderConfig, timeout: float = 10.0) -> None:
        self.config = config
        self.timeout = timeout
        self._metadata: dict[str, Any] | None = None
        self._metadata_loaded_at = 0.0
        self._jwks: dict[str, Any] | None = None

    @property
    def id(self) -> str:
        return self.config.id

    def _backchannel(self, url: str) -> str:
        """Переписывает публичный URL провайдера на внутренний."""
        internal = self.config.internal_issuer
        public = self.config.issuer
        if internal and url.startswith(public):
            return internal + url[len(public) :]
        return url

    async def _get_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self._backchannel(url), **kwargs)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.exception("OIDC request to %s failed", url)
            raise OIDCError() from exc

    async def metadata(self) -> dict[str, Any]:
        expired = time.monotonic() - self._metadata_loaded_at > METADATA_TTL_SECONDS
        if self._metadata is None or expired:
            self._metadata = await self._get_json(
                f"{self.config.issuer}/.well-known/openid-configuration"
            )
            self._metadata_loaded_at = time.monotonic()
        return self._metadata

    async def authorization_url(
        self, *, redirect_uri: str, state: str, nonce: str, code_verifier: str
    ) -> str:
        metadata = await self.metadata()
        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.config.scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": pkce_challenge(code_verifier),
            "code_challenge_method": "S256",
        }
        return f"{metadata['authorization_endpoint']}?{urlencode(params)}"

    async def exchange_code(
        self, *, code: str, redirect_uri: str, code_verifier: str
    ) -> dict[str, Any]:
        metadata = await self.metadata()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._backchannel(metadata["token_endpoint"]), data=data
                )
        except httpx.HTTPError as exc:
            logger.exception("OIDC token request failed")
            raise OIDCError() from exc
        if response.status_code != status.HTTP_200_OK:
            logger.warning(
                "OIDC token endpoint returned %s: %s",
                response.status_code,
                response.text[:500],
            )
            raise OIDCError("Провайдер отклонил код авторизации")
        return response.json()

    async def _signing_key(self, kid: str | None) -> jwt.PyJWK:
        for refresh in (False, True):
            if self._jwks is None or refresh:
                metadata = await self.metadata()
                self._jwks = await self._get_json(metadata["jwks_uri"])
            for key in self._jwks.get("keys", []):
                if key.get("use", "sig") != "sig":
                    continue
                if kid is None or key.get("kid") == kid:
                    return jwt.PyJWK(key)
        raise OIDCError("Ключ подписи провайдера не найден")

    async def verify_id_token(self, id_token: str, *, nonce: str) -> dict[str, Any]:
        metadata = await self.metadata()
        try:
            header = jwt.get_unverified_header(id_token)
            key = await self._signing_key(header.get("kid"))
            claims = jwt.decode(
                id_token,
                key,
                algorithms=["RS256", "ES256", "PS256"],
                audience=self.config.client_id,
                issuer=metadata["issuer"],
                leeway=30,
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.PyJWTError as exc:
            logger.warning("Invalid ID token from %s: %s", self.id, exc)
            raise OIDCError("Некорректный ID-токен провайдера") from exc
        if claims.get("nonce") != nonce:
            raise OIDCError("Некорректный nonce в ID-токене")
        return claims


class ProviderRegistry:
    def __init__(self, providers: list[OIDCProvider]) -> None:
        self._providers = {provider.id: provider for provider in providers}

    def get(self, provider_id: str) -> OIDCProvider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise AppError(
                "Провайдер авторизации не найден",
                code="unknown_provider",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return provider

    def all(self) -> list[OIDCProvider]:
        return list(self._providers.values())


@lru_cache
def get_provider_registry() -> ProviderRegistry:
    providers = []
    if settings.fsp_id_enabled:
        providers.append(
            OIDCProvider(
                OIDCProviderConfig(
                    id="fsp_id",
                    name="ФСП ID",
                    issuer=settings.fsp_id_issuer,
                    internal_issuer=settings.fsp_id_internal_issuer,
                    client_id=settings.fsp_id_client_id,
                    client_secret=settings.fsp_id_client_secret,
                )
            )
        )
    if settings.keycloak_enabled:
        providers.append(
            OIDCProvider(
                OIDCProviderConfig(
                    id="keycloak",
                    name="Keycloak",
                    issuer=settings.keycloak_issuer,
                    internal_issuer=settings.keycloak_internal_issuer,
                    client_id=settings.keycloak_client_id,
                    client_secret=settings.keycloak_client_secret,
                )
            )
        )
    return ProviderRegistry(providers)
