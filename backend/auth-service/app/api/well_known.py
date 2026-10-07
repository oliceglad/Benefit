"""Публичные метаданные для проверки токенов другими сервисами."""

from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.core.jwt import ALGORITHM, jwks

router = APIRouter(prefix="/.well-known", tags=["well-known"])


@router.get("/jwks.json")
async def get_jwks() -> dict[str, Any]:
    return jwks()


@router.get("/openid-configuration")
async def openid_configuration() -> dict[str, Any]:
    return {
        "issuer": settings.jwt_issuer,
        "jwks_uri": f"{settings.public_url}/.well-known/jwks.json",
        "id_token_signing_alg_values_supported": [ALGORITHM],
    }
