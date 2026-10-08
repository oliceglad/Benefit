"""Имитация ФСП ID для разработки и демонстрации.

Реализует минимальный OpenID Connect провайдер (Authorization Code + PKCE)
с той же структурой URL и claims, что у Keycloak, на котором будет работать
настоящий ФСП ID. Переход на боевой провайдер — смена ``FSP_ID_ISSUER``
и учётных данных клиента в auth-service.

Не для production: ключ подписи генерируется при старте, коды хранятся
в памяти процесса, пароль не спрашивается.
"""

import base64
import hashlib
import hmac
import html
import secrets
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, FastAPI, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jwt.algorithms import RSAAlgorithm
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    public_url: str = "http://localhost:8003"
    realm: str = "fsp"
    client_id: str = "benefit"
    client_secret: str = "fsp-dev-secret"
    redirect_uris: list[str] = [
        "http://localhost:8000/api/v1/auth/oauth/fsp_id/callback"
    ]
    token_ttl_seconds: int = 300
    code_ttl_seconds: int = 60

    @property
    def issuer(self) -> str:
        return f"{self.public_url}/realms/{self.realm}"


settings = Settings()


@dataclass(frozen=True)
class MockUser:
    sub: str
    family_name: str
    given_name: str
    middle_name: str
    email: str

    @property
    def name(self) -> str:
        return f"{self.family_name} {self.given_name} {self.middle_name}".strip()

    def claims(self) -> dict[str, Any]:
        return {
            "sub": self.sub,
            "email": self.email,
            "email_verified": True,
            "name": self.name,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "middle_name": self.middle_name,
            "preferred_username": self.email,
        }


MOCK_USERS = {
    user.sub: user
    for user in (
        MockUser(
            "c2f1a7e0-0001-4a5b-9c1d-000000000001",
            "Иванов",
            "Иван",
            "Иванович",
            "ivanov@fsp-test.ru",
        ),
        MockUser(
            "c2f1a7e0-0002-4a5b-9c1d-000000000002",
            "Петрова",
            "Анна",
            "Сергеевна",
            "petrova@fsp-test.ru",
        ),
        MockUser(
            "c2f1a7e0-0003-4a5b-9c1d-000000000003",
            "Смирнов",
            "Олег",
            "Петрович",
            "hr@romashka-test.ru",
        ),
    )
}


# Достижения участников в соревнованиях ФСП. Настоящий API ФСП пока
# неизвестен — формат выбран так, чтобы его было легко сопоставить.
MOCK_ACHIEVEMENTS: dict[str, list[dict[str, Any]]] = {
    "c2f1a7e0-0001-4a5b-9c1d-000000000001": [
        {
            "id": "ach-1001",
            "event": "Всероссийский чемпионат по продуктовому программированию",
            "discipline": "Продуктовое программирование",
            "level": "federal",
            "result": "winner",
            "place": 1,
            "team": "ByteForce",
            "date": "2025-11-23",
            "url": "https://fsp-russia.com/",
        },
        {
            "id": "ach-1002",
            "event": "Кубок России по спортивному программированию",
            "discipline": "Алгоритмическое программирование",
            "level": "federal",
            "result": "prize",
            "place": 3,
            "team": None,
            "date": "2025-04-12",
            "url": "https://fsp-russia.com/",
        },
        {
            "id": "ach-1003",
            "event": "Региональный хакатон «Цифровой прорыв»",
            "discipline": "Продуктовое программирование",
            "level": "regional",
            "result": "participant",
            "place": None,
            "team": "ByteForce",
            "date": "2024-09-30",
            "url": None,
        },
    ],
    "c2f1a7e0-0002-4a5b-9c1d-000000000002": [
        {
            "id": "ach-2001",
            "event": "Чемпионат России по информационной безопасности (CTF)",
            "discipline": "Информационная безопасность",
            "level": "federal",
            "result": "prize",
            "place": 2,
            "team": "NullPointer",
            "date": "2025-10-05",
            "url": "https://fsp-russia.com/",
        },
    ],
}


@dataclass
class AuthorizationCode:
    user: MockUser
    client_id: str
    redirect_uri: str
    nonce: str | None
    code_challenge: str | None
    expires_at: float


_codes: dict[str, AuthorizationCode] = {}


@lru_cache
def signing_key() -> tuple[rsa.RSAPrivateKey, dict[str, Any]]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk |= {"kid": secrets.token_hex(8), "use": "sig", "alg": "RS256"}
    return key, jwk


def sign(claims: dict[str, Any]) -> str:
    key, jwk = signing_key()
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": jwk["kid"]})


def oidc_error(error: str, description: str, code: int = 400) -> JSONResponse:
    return JSONResponse(
        {"error": error, "error_description": description}, status_code=code
    )


router = APIRouter(prefix=f"/realms/{settings.realm}")
OIDC = "/protocol/openid-connect"


@router.get("/.well-known/openid-configuration")
async def discovery() -> dict[str, Any]:
    base = f"{settings.issuer}{OIDC}"
    return {
        "issuer": settings.issuer,
        "authorization_endpoint": f"{base}/auth",
        "token_endpoint": f"{base}/token",
        "userinfo_endpoint": f"{base}/userinfo",
        "jwks_uri": f"{base}/certs",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "email", "profile"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_basic",
            "client_secret_post",
        ],
        "code_challenge_methods_supported": ["S256"],
    }


@router.get(f"{OIDC}/certs")
async def certs() -> dict[str, Any]:
    return {"keys": [signing_key()[1]]}


def _render_login(params: dict[str, str]) -> str:
    hidden = "".join(
        f'<input type="hidden" name="{k}" value="{html.escape(v)}">'
        for k, v in params.items()
    )
    users = "".join(
        f"""<button class="user" name="user_id" value="{u.sub}">
              <b>{html.escape(u.name)}</b><span>{html.escape(u.email)}</span>
            </button>"""
        for u in MOCK_USERS.values()
    )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ФСП ID — вход (тестовый стенд)</title>
<style>
  body {{ margin:0; font-family: system-ui, sans-serif; background:#eef2f7;
         color:#1f2933; display:flex; justify-content:center; padding:40px 16px; }}
  main {{ background:#fff; border-radius:16px; padding:32px; width:100%;
          max-width:420px; box-shadow:0 8px 24px rgba(15,23,42,.08); }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  .badge {{ display:inline-block; background:#fff4e5; color:#8a4b00;
            border-radius:6px; padding:2px 8px; font-size:12px; margin-bottom:20px; }}
  .user {{ display:flex; flex-direction:column; align-items:flex-start; width:100%;
           border:1px solid #d9e2ec; background:#f8fafc; border-radius:10px;
           padding:12px 14px; margin-bottom:8px; cursor:pointer; font:inherit; }}
  .user:hover {{ border-color:#2563eb; }}
  .user span {{ color:#616e7c; font-size:14px; }}
  fieldset {{ border:1px solid #d9e2ec; border-radius:10px; margin:16px 0 0;
              padding:12px 14px; }}
  input[type=text], input[type=email] {{ width:100%; box-sizing:border-box;
           margin:4px 0 10px; padding:8px; border:1px solid #cbd2d9;
           border-radius:6px; }}
  .primary {{ background:#2563eb; color:#fff; border:0; border-radius:8px;
              padding:10px 16px; font:inherit; cursor:pointer; }}
  .link {{ background:none; border:0; color:#616e7c; margin-top:16px;
           cursor:pointer; font:inherit; text-decoration:underline; }}
</style></head>
<body><main>
  <h1>Вход через ФСП ID</h1>
  <div class="badge">Тестовый стенд: имитация провайдера</div>
  <form method="post">{hidden}
    <p>Выберите тестового пользователя:</p>
    {users}
  </form>
  <form method="post">{hidden}
    <fieldset><legend>Или введите свои данные</legend>
      <label>Фамилия<input type="text" name="family_name" required></label>
      <label>Имя<input type="text" name="given_name" required></label>
      <label>Почта<input type="email" name="email" required></label>
      <button class="primary" name="user_id" value="custom">Войти</button>
    </fieldset>
  </form>
  <form method="post">{hidden}
    <button class="link" name="action" value="cancel">Отменить вход</button>
  </form>
</main></body></html>"""


def _validate_client(client_id: str, redirect_uri: str) -> None:
    if client_id != settings.client_id or redirect_uri not in settings.redirect_uris:
        # Ошибку показываем на странице: редиректить на непроверенный URI нельзя.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Неизвестный client_id или redirect_uri"
        )


@router.get(f"{OIDC}/auth", response_class=HTMLResponse)
async def authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    scope: str = "",
    state: str = "",
    nonce: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
) -> HTMLResponse:
    _validate_client(client_id, redirect_uri)
    if response_type != "code" or "openid" not in scope.split():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ожидается OIDC code flow")
    if code_challenge and code_challenge_method != "S256":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Поддерживается только S256")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
    }
    return HTMLResponse(_render_login(params))


@router.post(f"{OIDC}/auth")
async def authorize_submit(
    client_id: Annotated[str, Form()],
    redirect_uri: Annotated[str, Form()],
    state: Annotated[str, Form()] = "",
    nonce: Annotated[str, Form()] = "",
    code_challenge: Annotated[str, Form()] = "",
    user_id: Annotated[str, Form()] = "",
    action: Annotated[str, Form()] = "",
    family_name: Annotated[str, Form()] = "",
    given_name: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
) -> RedirectResponse:
    _validate_client(client_id, redirect_uri)

    def back(**params: str) -> RedirectResponse:
        query = urlencode({**params, "state": state} if state else params)
        return RedirectResponse(f"{redirect_uri}?{query}", status.HTTP_302_FOUND)

    if action == "cancel":
        return back(error="access_denied")

    if user_id == "custom":
        email = email.strip().lower()
        sub = hashlib.sha256(email.encode()).hexdigest()[:32]
        user = MockUser(sub, family_name.strip(), given_name.strip(), "", email)
    elif user_id in MOCK_USERS:
        user = MOCK_USERS[user_id]
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Пользователь не выбран")

    code = secrets.token_urlsafe(32)
    _codes[code] = AuthorizationCode(
        user=user,
        client_id=client_id,
        redirect_uri=redirect_uri,
        nonce=nonce or None,
        code_challenge=code_challenge or None,
        expires_at=time.time() + settings.code_ttl_seconds,
    )
    return back(code=code)


def _client_credentials(
    authorization: str | None, client_id: str, client_secret: str
) -> tuple[str, str]:
    if authorization and authorization.lower().startswith("basic "):
        decoded = base64.b64decode(authorization[6:]).decode()
        client_id, _, client_secret = decoded.partition(":")
    return client_id, client_secret


@router.post(f"{OIDC}/token")
async def token(
    grant_type: Annotated[str, Form()],
    code: Annotated[str, Form()] = "",
    redirect_uri: Annotated[str, Form()] = "",
    code_verifier: Annotated[str, Form()] = "",
    client_id: Annotated[str, Form()] = "",
    client_secret: Annotated[str, Form()] = "",
    authorization: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    client_id, client_secret = _client_credentials(
        authorization, client_id, client_secret
    )
    if client_id != settings.client_id or not hmac.compare_digest(
        client_secret, settings.client_secret
    ):
        return oidc_error("invalid_client", "Invalid client credentials", 401)
    if grant_type != "authorization_code":
        return oidc_error("unsupported_grant_type", grant_type)

    stored = _codes.pop(code, None)
    if (
        stored is None
        or stored.expires_at < time.time()
        or stored.client_id != client_id
        or stored.redirect_uri != redirect_uri
    ):
        return oidc_error("invalid_grant", "Code not valid")
    if stored.code_challenge:
        digest = hashlib.sha256(code_verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        if not hmac.compare_digest(challenge, stored.code_challenge):
            return oidc_error("invalid_grant", "PKCE verification failed")

    now = int(time.time())
    common = {
        "iss": settings.issuer,
        "iat": now,
        "exp": now + settings.token_ttl_seconds,
        "auth_time": now,
        "azp": client_id,
        "jti": secrets.token_hex(16),
        **stored.user.claims(),
    }
    id_claims = {**common, "aud": client_id, "typ": "ID"}
    if stored.nonce:
        id_claims["nonce"] = stored.nonce
    id_token = sign(id_claims)
    access_token = sign(
        {**common, "aud": "account", "typ": "Bearer", "scope": "openid email profile"}
    )
    return JSONResponse(
        {
            "access_token": access_token,
            "id_token": id_token,
            "token_type": "Bearer",
            "expires_in": settings.token_ttl_seconds,
            "scope": "openid email profile",
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get(f"{OIDC}/userinfo")
async def userinfo(request: Request) -> JSONResponse:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return oidc_error("invalid_token", "Missing bearer token", 401)
    key, _ = signing_key()
    try:
        claims = jwt.decode(
            header[7:], key.public_key(), algorithms=["RS256"], audience="account"
        )
    except jwt.PyJWTError:
        return oidc_error("invalid_token", "Token is not valid", 401)
    fields = ("sub", "email", "email_verified", "name", "given_name", "family_name")
    return JSONResponse({k: claims[k] for k in fields if k in claims})


participants_router = APIRouter(prefix="/api/v1/participants", tags=["participants"])


@participants_router.get("/{sub}/achievements")
async def participant_achievements(
    sub: str, authorization: Annotated[str | None, Header()] = None
) -> JSONResponse:
    """Достижения участника. Доступно клиенту по client_id/client_secret."""
    client_id, client_secret = _client_credentials(authorization, "", "")
    if client_id != settings.client_id or not hmac.compare_digest(
        client_secret, settings.client_secret
    ):
        return oidc_error("invalid_client", "Invalid client credentials", 401)
    return JSONResponse(
        {"participant_id": sub, "items": MOCK_ACHIEVEMENTS.get(sub, [])}
    )


app = FastAPI(title="FSP ID (mock)")
app.include_router(router)
app.include_router(participants_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
