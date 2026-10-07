# Benefit

Сервис подбора кандидатов на вакансии. Микросервисная архитектура.

## Стек

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic
- **БД:** PostgreSQL 17 (FTS, pg_trgm, pgvector); у каждого сервиса своя база
- **Аутентификация:** собственный auth-service (JWT RS256 + JWKS), Keycloak, ФСП ID (OIDC)
- **Frontend:** в разработке

## Структура

```
benefit/
├── backend/
│   ├── gateway/             # API-шлюз (nginx): единая точка входа, rate limiting
│   ├── core/                # основной сервис (вакансии, подбор)
│   ├── auth-service/        # регистрация, вход, токены, RBAC
│   ├── mail-service/        # отправка писем (SMTP)
│   ├── fsp-id-mock/         # имитация ФСП ID для разработки
│   └── keycloak/            # realm Keycloak (импортируется при старте)
├── frontend/                # клиентское приложение (в разработке)
├── docker-compose.yml
└── .env.example
```

## Запуск

```bash
cp .env.example .env
docker compose up --build
```

Все запросы к API идут через шлюз на http://localhost:8000. Сервисы
за ним наружу не публикуются.

| Что                       | Адрес                                   |
|---------------------------|-----------------------------------------|
| Core API / Swagger        | http://localhost:8000/docs              |
| Auth API / Swagger        | http://localhost:8000/api/v1/auth/docs  |
| Mailpit (входящие письма) | http://localhost:8025                   |
| ФСП ID (mock)             | http://localhost:8003                   |
| Keycloak (admin/admin)    | http://localhost:8080                   |

Маршрутизация шлюза: `/api/v1/auth/*`, `/api/v1/users/*`, `/.well-known/*` →
auth-service, всё остальное → core.

Ограничение частоты запросов (по IP): `login`, `register`, `verify-email`,
`resend-code`, `oauth/exchange` — 10 в минуту (с запасом в 5 запросов),
остальное API — 20 в секунду. При превышении шлюз отвечает `429` с
`{"error": {"code": "rate_limited", ...}}` и заголовком `Retry-After`.

Миграции применяются автоматически при старте контейнеров core и auth-service.

## Аутентификация и роли

Роли (RBAC): `candidate` — кандидат, `employer` — работодатель.

auth-service выпускает access-токен (JWT, RS256, 15 мин) и refresh-токен
(30 дней, одноразовый, с ротацией). Формат access-токена совместим с Keycloak:
роли лежат в `realm_access.roles`. Остальные сервисы проверяют токены сами
по публичному ключу из `GET /.well-known/jwks.json` — пример в
`backend/core/app/core/security.py` и зависимость `require_roles` в `backend/core/app/api/deps.py`:

```python
@router.post("/vacancies")
async def create_vacancy(
    user: Annotated[Principal, Depends(require_roles(Role.EMPLOYER))],
): ...
```

### Способы входа

**1. Почта и пароль** (только российские домены: `.ru`, `.su`, `.рф`)

```
POST /api/v1/auth/register      {email, password, role, full_name?}  → на почту уходит 6-значный код
POST /api/v1/auth/verify-email  {email, code}                         → пара токенов
POST /api/v1/auth/resend-code   {email}                               → новый код (раз в 60 с)
POST /api/v1/auth/login         {email, password}                     → пара токенов
POST /api/v1/auth/refresh       {refresh_token}                       → новая пара токенов
POST /api/v1/auth/logout        {refresh_token}
GET  /api/v1/users/me           (Bearer)
```

Код действует 10 минут, на ввод даётся 5 попыток. Локально письма
смотрите в Mailpit: http://localhost:8025.

**2. ФСП ID** (имитация) и **3. Keycloak** — OpenID Connect, Authorization Code + PKCE:

```
GET  /api/v1/auth/providers                                  → список провайдеров для кнопок
GET  /api/v1/auth/oauth/{fsp_id|keycloak}/authorize?role=…   → редирект на страницу входа
     … провайдер возвращает браузер на фронтенд: OAUTH_FRONTEND_CALLBACK_URL?code=… (или ?error=…)
POST /api/v1/auth/oauth/exchange  {code}                     → пара токенов
```

`role` нужен только при первом входе, если провайдер сам не передал роль
(Keycloak передаёт realm-роли). Аккаунт с той же почтой привязывается
автоматически, только если провайдер подтвердил почту.

Пока фронтенда нет, `OAUTH_FRONTEND_CALLBACK_URL` пустой и браузер попадает на
отладочную страницу auth-service, которая сразу показывает токены. Попробуйте
открыть в браузере:

- http://localhost:8000/api/v1/auth/oauth/fsp_id/authorize?role=candidate
- http://localhost:8000/api/v1/auth/oauth/keycloak/authorize — тестовые пользователи
  `candidate@benefit-test.ru` / `candidate123`, `employer@benefit-test.ru` / `employer123`

### Переход на настоящий ФСП ID

ФСП ID будет работать на Keycloak, а mock повторяет его URL и claims
(`/realms/<realm>/protocol/openid-connect/...`). Для перехода достаточно
задать в auth-service `FSP_ID_ISSUER`, `FSP_ID_CLIENT_ID`,
`FSP_ID_CLIENT_SECRET` и зарегистрировать redirect URI
`<AUTH_PUBLIC_URL>/api/v1/auth/oauth/fsp_id/callback` у провайдера.

## Тесты

```bash
# auth-service: нужен запущенный auth-db (docker compose up -d auth-db)
cd backend/auth-service && pip install -e '.[dev]' && pytest
```

Остальные сервисы тестируются так же, без внешних зависимостей.
