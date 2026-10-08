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
│   ├── candidate-service/   # личный кабинет кандидата: профиль, резюме, PDF
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
| Candidate API / Swagger   | http://localhost:8000/api/v1/candidates/docs |
| Mailpit (входящие письма) | http://localhost:8025                   |
| ФСП ID (mock)             | http://localhost:8003                   |
| Keycloak (admin/admin)    | http://localhost:8080                   |

Маршрутизация шлюза: `/api/v1/auth/*`, `/api/v1/users/*`, `/.well-known/*` →
auth-service, `/api/v1/candidates/*` → candidate-service, всё остальное → core.
Внутренние API сервисов (`/internal/*`) через шлюз недоступны.

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

Привязать ФСП ID к уже существующему аккаунту: `POST /api/v1/auth/oauth/fsp_id/link`
(с Bearer-токеном) возвращает `authorization_url`; после входа браузер вернётся
на фронтенд с `?linked=fsp_id`. Список привязок — `GET /api/v1/users/me/identities`.

### Переход на настоящий ФСП ID

ФСП ID будет работать на Keycloak, а mock повторяет его URL и claims
(`/realms/<realm>/protocol/openid-connect/...`). Для перехода достаточно
задать в auth-service `FSP_ID_ISSUER`, `FSP_ID_CLIENT_ID`,
`FSP_ID_CLIENT_SECRET` и зарегистрировать redirect URI
`<AUTH_PUBLIC_URL>/api/v1/auth/oauth/fsp_id/callback` у провайдера.

## Личный кабинет кандидата (candidate-service)

Доступен только роли `candidate` и только для собственного профиля; работодатели
видят опубликованные профили с учётом настроек приватности, кандидаты чужие
профили не видят.

```
GET    /api/v1/candidates/me                 профиль (при первом входе создаётся черновик)
PATCH  /api/v1/candidates/me                 частичное сохранение — можно по шагам онбординга
POST   /api/v1/candidates/me/publish         публикация (нужны обязательные поля и согласия)
POST   /api/v1/candidates/me/unpublish
DELETE /api/v1/candidates/me                 удаление профиля
PUT|GET|DELETE /api/v1/candidates/me/photo   фото (JPEG/PNG/WebP до 5 МБ, EXIF удаляется)
GET|POST /api/v1/candidates/me/consents      согласия: обработка ПДн и публикация (с версией)
DELETE /api/v1/candidates/me/consents/{type} отзыв согласия — профиль снимается с публикации
POST   /api/v1/candidates/me/fsp/sync        связь с участником ФСП и загрузка достижений
POST   /api/v1/candidates/me/resume/import   распознать PDF-резюме (?apply=true — дополнить профиль)
GET    /api/v1/candidates/me/resume.pdf      экспорт резюме в PDF
GET    /api/v1/candidates/dictionaries       справочники: грейды, роли, уровни, форматы…
GET    /api/v1/candidates/dictionaries/skills?q=  подсказки навыков («питон» → Python)
GET    /api/v1/candidates/{user_id}          профиль для работодателя (+ /photo, /resume.pdf)
```

Поле `completeness` в профиле содержит процент заполнения, недостающие поля
и шаги онбординга (`personal → contacts → specialization → skills → experience →
preferences → consents`) — по нему фронтенд ведёт нового пользователя.

**Состав профиля:** ФИО, дата рождения (показывается возраст), город и готовность
к переезду, контакты (телефон, почта, Telegram, GitHub/Хабр и др.), желаемая
должность, грейд (заявленный и подтверждённый тестированием), IT-роли, стек с
уровнем и стажем по каждому навыку, софт-скиллы, языки (CEFR), опыт работы
(с достижениями и стеком), образование, курсы, пет-проекты, зарплатные ожидания,
занятость, формат работы, статус поиска, достижения ФСП, фото, настройки
приватности. Навыки нормализуются по каталогу синонимов, чтобы подбор вакансий
сравнивал одинаковые названия.

**Импорт PDF** понимает резюме hh.ru, Хабр Карьеры и собственный экспорт Benefit
и возвращает черновик для проверки пользователем. Парсер эвристический
и заменяемый (`ResumeParser`), например на разбор с помощью LLM.

### Задел для будущих сервисов

Внутренний API candidate-service (с `X-Internal-Token`):

- `GET /internal/v1/candidates`, `GET /internal/v1/candidates/{id}` — снимки
  профилей для сервиса подбора вакансий;
- `PUT /internal/v1/candidates/{id}/verified-grade` — запись грейда,
  подтверждённого сервисом тестирования;
- `GET /internal/v1/events?after_id=` — лента событий (`candidate.profile.published`,
  `.updated`, `.unpublished`, `.deleted`, `candidate.grade.verified`,
  `candidate.fsp_achievements.synced`). События пишутся в outbox в одной
  транзакции с изменением; при появлении брокера их можно транслировать туда.

## Тесты

```bash
# auth-service: нужен запущенный auth-db (docker compose up -d auth-db)
cd backend/auth-service && pip install -e '.[dev]' && pytest
```

candidate-service: нужен `candidate-db` (`docker compose up -d candidate-db`), а для
экспорта PDF — Pango (в Docker уже есть; на macOS: `brew install pango` и запуск
с `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`). Остальные сервисы тестируются
так же, без внешних зависимостей.
