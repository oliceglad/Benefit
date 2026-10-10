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
│   ├── assessment-service/  # опрос и тестирование: подтверждение грейда
│   ├── applications-service/# приглашения, отклики, процесс найма
│   ├── notification-service/# уведомления в кабинете + дублирование на почту
│   ├── chat-service/        # переписка (WebSocket), файлы, регулярные задания
│   ├── employer-service/    # профиль компании, потребности, вакансии
│   ├── matching-service/    # банк кандидатов: поиск и подборка с обоснованием
│   ├── mail-service/        # отправка писем (SMTP)
│   ├── fsp-id-mock/         # имитация ФСП ID для разработки
│   ├── keycloak/            # realm Keycloak (импортируется при старте)
│   ├── libs/benefit-common/ # общий код: JWT/RBAC, внутренний API, outbox, справочники
│   └── e2e/                 # сквозной smoke-тест связности сервисов
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
| Фронтенд (SPA)            | http://localhost:3000                   |
| Core API / Swagger        | http://localhost:8000/docs              |
| Auth API / Swagger        | http://localhost:8000/api/v1/auth/docs  |
| Candidate API / Swagger   | http://localhost:8000/api/v1/candidates/docs |
| Assessment API / Swagger  | http://localhost:8000/api/v1/assessments/docs |
| Invitations API / Swagger | http://localhost:8000/api/v1/invitations/docs |
| Notifications / Swagger   | http://localhost:8000/api/v1/notifications/docs |
| Chat / Swagger            | http://localhost:8000/api/v1/chat/docs |
| Employers / Swagger       | http://localhost:8000/api/v1/employers/docs |
| Talent (поиск) / Swagger  | http://localhost:8000/api/v1/talent/docs |
| Mailpit (входящие письма) | http://localhost:8025                   |
| Grafana (admin / benefit-grafana) | http://localhost:3001           |
| Prometheus                | http://localhost:9090                   |
| Alertmanager              | http://localhost:9093                   |
| ФСП ID (mock)             | http://localhost:8003                   |
| Keycloak (admin/admin)    | http://localhost:8080                   |

Маршрутизация шлюза: `/api/v1/auth/*`, `/api/v1/users/*`, `/.well-known/*` →
auth-service, `/api/v1/candidates/*` → candidate-service, `/api/v1/assessments/*` →
assessment-service, `/api/v1/invitations*` → applications-service,
`/api/v1/notifications*` → notification-service, `/api/v1/chat/*` (включая
WebSocket `/api/v1/chat/ws`) → chat-service, `/api/v1/employers/*` и
`/api/v1/vacancies*` → employer-service, `/api/v1/talent/*` → matching-service,
`/api/v1/applications*` и `/api/v1/hiring/*` → applications-service, всё
остальное → core.
Внутренние API сервисов (`/internal/*`) через шлюз недоступны.

Ограничение частоты запросов (по IP): `login`, `register`, `verify-email`,
`resend-code`, `oauth/exchange` — 10 в минуту (с запасом в 5 запросов),
остальное API — 20 в секунду. При превышении шлюз отвечает `429` с
`{"error": {"code": "rate_limited", ...}}` и заголовком `Retry-After`.

Миграции применяются автоматически при старте контейнеров; assessment-service
также импортирует новые пакеты тестов из `backend/assessment-service/content/`
(см. «Контент тестов»). Сервисы стартуют по healthcheck'ам
в порядке зависимостей.

Проверить, что все сервисы связаны и работают вместе:

```bash
python backend/e2e/smoke_test.py   # нужны пакеты httpx и httpx-ws
```

## CI/CD и сервер

Workflow `.github/workflows/ci-cd.yml` запускается на каждый push и PR:

- **Бэкенд:** ruff (lint и формат); тесты каждого сервиса отдельной задачей
  на чистом PostgreSQL.
- **Фронтенд:** eslint, typecheck, vitest, сборка.
- **Деплой** на сервер `DEPLOY_HOST`: только из `main` и только после зелёных проверок,
  также вручную через «Run workflow». Код копируется по SSH (rsync) в
  `/opt/benefit`, затем на сервере выполняется `.github/scripts/deploy.sh`:
  `docker compose up -d --build`, ожидание healthy и проверка
  `/api/v1/status` через фронтенд.

Настройка один раз — GitHub → Settings → Secrets and variables → Actions:

| Где | Имя | Значение |
|---|---|---|
| Variables | `DEPLOY_HOST` | адрес сервера (IP или домен) |
| Variables | `DEPLOY_KNOWN_HOSTS` | ключи сервера — вывод `ssh-keyscan <DEPLOY_HOST>` |
| Secrets | `DEPLOY_SSH_KEY` | приватный ключ, с которым пускает `root@<DEPLOY_HOST>` |

Чтобы переехать на другой сервер, поменяйте `DEPLOY_HOST` и
`DEPLOY_KNOWN_HOSTS`, правки в коде не нужны. Без `DEPLOY_KNOWN_HOSTS`
деплой не запустится: по этим ключам проверяется, что код уходит на наш
сервер, а не на подменённый.

На сервере (`<DEPLOY_HOST>` — адрес из переменной):

| Что | Адрес |
|---|---|
| Фронтенд | http://<DEPLOY_HOST>/ |
| Swagger | http://<DEPLOY_HOST>/docs, `http://<DEPLOY_HOST>/api/v1/<сервис>/docs` |
| Шлюз, Grafana, Prometheus, Mailpit, базы | только `127.0.0.1` на сервере — через SSH-туннель |

Снаружи открыт только фронтенд: он отдаёт SPA и проксирует на шлюз `/api`,
`/docs`, `/.well-known` (тот же origin, CORS не нужен). Лимиты шлюз считает
по реальному IP клиента из `X-Forwarded-For` — заголовку верит только от
адресов внутренней сети Docker.

- **`.env`.** При первом деплое скрипт ставит Docker и создаёт
  `/opt/benefit/.env` со случайными паролями и секретами. Дальше `.env` не
  перезаписывается — меняйте его на сервере вручную.
- **`APP_ENV=local`.** Сервер работает по HTTP, а `production` требует HTTPS
  (Secure-cookie). Поэтому `APP_ENV=local`, но `DEBUG=false`.
- **Пакеты тестов** в git нет, на сервер их нужно положить вручную, затем
  перезапустить сервис:

  ```bash
  scp backend/assessment-service/content/*.json root@<DEPLOY_HOST>:/opt/benefit/backend/assessment-service/content/
  ssh root@<DEPLOY_HOST> 'cd /opt/benefit && docker compose restart assessment-service'
  ```

- Grafana и письма (Mailpit) — через туннель:
  `ssh -L 3001:127.0.0.1:3001 -L 8025:127.0.0.1:8025 root@<DEPLOY_HOST>`.

## Мониторинг (Prometheus, Grafana, Alertmanager)

Стек поднимается вместе с `docker compose up`. Конфигурация лежит в
`backend/monitoring`.

**Что собирается:**
- **Сервисы** (`GET /metrics` во внутренней сети; через шлюз — 404).
  Метрики подключаются в `benefit_common.setup_app`, поэтому есть у каждого
  сервиса:
  - `benefit_http_requests_total`, `benefit_http_request_duration_seconds` —
    запросы и время по методу, шаблону маршрута
    (`/api/v1/employers/vacancies/{vacancy_id}`) и статусу;
  - `benefit_app_errors_total{code,status}` — ошибки по коду из единого
    формата: `invalid_credentials`, `upstream_unavailable`,
    `database_unavailable`, …;
  - `benefit_upstream_requests_total{target,outcome}` — вызовы соседних
    сервисов: `ok`, `client_error`, `server_error`, `timeout`, `unavailable`;
  - `benefit_outbox_*` — доставка событий между сервисами (доставлено,
    повторы, отброшено), очередь и возраст старейшего события;
  - `benefit_websocket_connections`, `benefit_websocket_users` — чат онлайн.
- **Базы данных** — postgres-exporter, все 9 баз: доступность, подключения,
  транзакции, размер.
- **Шлюз** — nginx-exporter (`stub_status` на порту 8081, только в сети
  docker).

**Дашборды Grafana** (папка Benefit):
- «Benefit — сервисы»: состояние, RPS, 5xx, p95, активные алерты, ошибки по
  кодам, медленные маршруты, связи сервисов, outbox, входы, чат. Фильтр по
  сервису.
- «Benefit — инфраструктура»: PostgreSQL и шлюз.

**Алерты** (`backend/monitoring/prometheus/alerts.yml`) уходят письмом через
Alertmanager, локально — в Mailpit:

| Алерт | Когда |
|---|---|
| ServiceDown / GatewayDown / PostgresDown | сервис, шлюз или база не отвечает больше минуты |
| DatabaseErrors | запросы падают с «База данных недоступна» |
| HighErrorRate | больше 5% ответов 5xx за 5 минут |
| InternalErrors | необработанные исключения (искать в логах по request_id) |
| HighLatency | p95 больше 1 с в течение 10 минут |
| UpstreamFailures | сервис не может достучаться до соседа |
| OutboxStuck / OutboxDeliveryFailed | события не доставляются больше 10 минут или отброшены |
| MailUnavailable | письма (коды подтверждения) не отправляются |
| CompanyRegistryUnavailable | реестр ФНС недоступен |
| LoginBruteForce / CsrfRejections | перебор паролей и кодов, запросы без CSRF |
| PostgresConnectionsHigh | занято больше 80% подключений |

Получатель и SMTP задаются в `.env`: `ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM`,
`ALERT_SMTP_HOST`, `ALERT_SMTP_USER`, `ALERT_SMTP_PASSWORD`,
`ALERT_SMTP_REQUIRE_TLS`. Пароль Grafana — `GRAFANA_ADMIN_PASSWORD`, его
нужно сменить в production. Grafana, Prometheus и Alertmanager опубликованы
только на 127.0.0.1.

## Ошибки и диагностика

Все сервисы и шлюз отвечают ошибками в одном формате:

```json
{"error": {
  "code": "upstream_unavailable",
  "message": "Сервис профилей кандидатов недоступен. Попробуйте повторить запрос позже",
  "service": "candidate-service",
  "request_id": "662215a2d79ee7a33c22bb941454abc4",
  "details": [{"field": "email", "message": "некорректный адрес почты"}]
}}
```

* `service` — где ошибка **произошла**: если сервис не дождался соседа,
  указан сосед; если сервис не запущен — ответ шлюза с его названием.
* `request_id` (и заголовок `X-Request-ID`) — сквозной ID: шлюз присваивает
  его запросу, он передаётся во все межсервисные вызовы и пишется в логи
  каждого сервиса. Найти всю цепочку:
  `docker compose logs | grep <request_id>`.
* Ошибки валидации — по полям, на русском (`details`); непредвиденные —
  без деталей реализации (стектрейс только в логе).
* `GET /api/v1/status` — состояние всех сервисов и время их ответа.

Результаты аудита безопасности — в [backend/SECURITY.md](backend/SECURITY.md).

## Связь сервисов

```
               ┌──────────── gateway (nginx, :8000) ────────────┐
               │                                                │
 auth ◄─JWKS── candidate ◄──── assessment ────► notification ──► mail ──► SMTP
  ▲              ▲  │              │                ▲
  │ identities   │  └─ ФСП API     │                │
  └──────────────┘                 │      applications
                                   └─ outbox ──────┘ (outbox)
```

- Все сервисы проверяют JWT auth-service сами (JWKS), роли — `realm_access.roles`.
- Межсервисные вызовы идут во внутренний API (`/internal/v1/*`) с заголовком
  `X-Internal-Token`; шлюз этот путь не пропускает.
- Вызовы, которые нельзя потерять (результат теста → профиль, уведомления),
  пишутся в outbox в одной транзакции с изменением и доставляются фоново с
  повторами. Получатели идемпотентны (`dedup_key` в уведомлениях), поэтому
  повторная доставка не создаёт дублей.
- Общий код и справочники (грейды, специализации, отрасли) — в
  `backend/libs/benefit-common`, чтобы контракты не расходились между сервисами.

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

### Токены в cookie (для браузера)

Вход, подтверждение почты, обмен OAuth-кода и обновление токенов
поддерживают два режима:

* по умолчанию токены возвращаются в теле ответа (Swagger, мобильные клиенты,
  межсервисные вызовы) и передаются в заголовке `Authorization: Bearer`;
* с заголовком **`X-Auth-Mode: cookie`** токены выставляются в cookie и в теле
  не возвращаются (скрипт на странице их не прочитает):

| Cookie | Атрибуты | Назначение |
|---|---|---|
| `benefit_access` | HttpOnly, SameSite=Strict, `Path=/` | access-токен — принимают все сервисы |
| `benefit_refresh` | HttpOnly, SameSite=Strict, `Path=/api/v1/auth` | refresh-токен — уходит только в auth-service |
| `benefit_csrf` | SameSite=Strict, читается JS | значение для заголовка `X-CSRF-Token` |

Изменяющие запросы (POST/PUT/PATCH/DELETE), авторизованные cookie, должны
содержать заголовок `X-CSRF-Token` со значением cookie `benefit_csrf`
(double-submit CSRF); без него — `403`. `POST /api/v1/auth/refresh` и
`/logout` без тела берут refresh-токен из cookie; logout удаляет cookie.
WebSocket чата авторизуется по cookie автоматически, если Origin в
`TRUSTED_ORIGINS`. В production обязателен `COOKIE_SECURE=true` (HTTPS).

Фронтенд лучше отдавать через тот же шлюз (один origin). Для разработки на
`localhost:3000` шлюз отвечает на CORS с `credentials`.

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

### Управление аккаунтом

```
POST  /api/v1/auth/password/forgot      {email} → код на почту (ответ 202 для любого адреса)
POST  /api/v1/auth/password/reset       {email, code, new_password} → 204, все сессии завершаются
GET   /api/v1/users/me                  аккаунт (+ has_password)
PATCH /api/v1/users/me                  {full_name}
POST  /api/v1/users/me/password         {current_password, new_password} → новые токены
POST  /api/v1/users/me/email            {new_email, password} → код на новый адрес
POST  /api/v1/users/me/email/confirm    {code} → новые токены
POST  /api/v1/users/me/delete-code      код подтверждения удаления на почту
POST  /api/v1/users/me/delete           {password} или {code} → 204, cookie очищаются
```

- **Восстановление пароля** не раскрывает, есть ли аккаунт: ответ всегда 202.
  Им же задаёт первый пароль пользователь, который входил только через
  ФСП ID. Код действует 15 минут, на него даётся 5 попыток.
- **Смена пароля и почты** завершает остальные сессии, текущая получает новые
  токены (в режиме cookie — в cookie). На почту уходит предупреждение, при
  смене адреса — на старый.
- **Почта меняется в два шага:** код приходит на новый адрес, и до его ввода
  остаётся прежняя почта. Действуют те же правила, что при регистрации
  (российские домены, адрес не занят).
- **Подтверждение.** Смену почты и удаление аккаунт с паролем подтверждает
  паролем. Аккаунт без пароля (`has_password: false`) подтверждает удаление
  кодом из письма.
- **Удаление.** Аккаунт удаляется в auth-service сразу, почта освобождается.
  Каждый сервис получает событие через outbox (с повторами, пока не
  подтвердит) и удаляет свои данные:
  - профиль кандидата с фото и доступами к контактам;
  - компанию и вакансии;
  - отклики, приглашения и процессы найма;
  - переписку с файлами;
  - уведомления и очередь писем;
  - попытки и тесты;
  - запись в поиске.

  Журнал согласий сохраняется с отметкой об отзыве как подтверждение
  законности обработки.

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
- `PUT /internal/v1/candidates/{id}/assessment` — категория по итогам
  тестирования (присылает assessment-service);
- `GET /internal/v1/events?after_id=` — лента событий (`candidate.profile.published`,
  `.updated`, `.unpublished`, `.deleted`, `candidate.grade.verified`,
  `candidate.fsp_achievements.synced`). События пишутся в outbox в одной
  транзакции с изменением; при появлении брокера их можно транслировать туда.

## Тестирование грейда (assessment-service)

```
GET  /api/v1/assessments/survey                     опрос: отрасли, специализации, грейды + предзаполнение из профиля
POST /api/v1/assessments/attempts                   начать: {industry, specialization, target_grade, years_of_experience, skills}
GET  /api/v1/assessments/attempts/{id}/current-task текущая задача (запускает её таймер)
POST /api/v1/assessments/attempts/{id}/answers      ответ {attempt_task_id, answer} (null — пропустить)
POST /api/v1/assessments/attempts/{id}/finish       досрочно завершить
GET  /api/v1/assessments/attempts/{id}              состояние / результат
GET  /api/v1/assessments/attempts                   история опросов и тестов
GET  /api/v1/assessments/status                     подтверждённая категория, уровни навыков, кулдауны
GET  /api/v1/assessments/skill-tests                тесты на навыки: шкала, текущий уровень, когда можно повторить
POST /api/v1/assessments/skill-tests/{id}/attempts  начать тест на навык (дальше — те же current-task/answers)
GET  /api/v1/assessments/tests?kind=grade|skill     каталог тестов
```

- Задачи выдаются по одной; у каждой — баллы и лимит времени. Время каждой
  задачи и всего теста считает сервер; ответ после лимита задачи — 0 баллов,
  по истечении времени теста попытка завершается автоматически.
- Задачи подбираются из банка теста с приоритетом навыков кандидата;
  множественный выбор оценивается частично.
- **Итог** (пороги в настройках): меньше 75% — грейд **не подтверждён**
  (низкий грейд нигде не показывается: работодатель видит заявленный грейд с
  пометкой «не подтверждён»); от 75% — подтверждён целевой грейд; от 90% —
  подтверждён грейд на ступень выше заявленного.
- Подтверждение действует 365 дней; в профиль идёт лучший действующий
  результат, поэтому неудачная попытка на грейд выше не отменяет уже
  подтверждённый. Повтор в той же специализации — раз в 7 дней.
- Результат: категория в профиле кандидата (отрасль, специализация, грейд,
  статус) + уведомление в кабинете и на почту.
- Для каждой пары «специализация + грейд» активен один тест (иначе импорт и
  админка отвечают `409 assessment_duplicate`).

### Тесты на навыки

Кроме теста на грейд, кандидат может подтвердить отдельный навык: английский,
SQL, Git, Linux, Docker, алгоритмы. Такой тест (`kind: "skill"`) не привязан
к специализации, опроса перед ним нет.

- Уровень определяется по шкале теста: подтверждается самая высокая ступень,
  порог которой набран. У английского шкала CEFR (A2 от 30%, B1 от 50%,
  B2 от 70%, C1 от 85%), у остальных — «Базовый», «Уверенный», «Продвинутый»
  (от 40, 65 и 85%). Ниже первой ступени уровень не подтверждается и нигде не
  показывается.
- Как и грейд, уровень действует 365 дней, в профиль идёт лучший действующий
  результат, повтор того же навыка — раз в 7 дней. Тест на навык не влияет
  на грейд и его кулдаун.
- Подтверждённые уровни видны в профиле (`verified_skills`) и работодателю.
  В подборе такой навык засчитывается полностью, даже если кандидат не указал
  его в стеке: в обосновании — «English — подтверждён тестом: B2».

### Каталог тестов

| Тест | Вид | Задач в банке / в попытке | Время |
|---|---|---|---|
| Backend — Junior | грейд | 14 / 10 | 15 мин |
| Python Backend — Middle | грейд | 12 / 8 | 20 мин |
| Backend — Senior | грейд | 14 / 10 | 25 мин |
| Frontend — Junior | грейд | 13 / 10 | 15 мин |
| Frontend — Middle | грейд | 13 / 10 | 20 мин |
| Fullstack — Middle | грейд | 13 / 10 | 20 мин |
| Mobile — Middle | грейд | 13 / 10 | 20 мин |
| DevOps — Middle | грейд | 14 / 10 | 20 мин |
| QA (ручное тестирование) — Junior | грейд | 13 / 10 | 15 мин |
| QA Automation — Junior | грейд | 10 / 8 | 15 мин |
| Аналитик данных — Junior | грейд | 13 / 10 | 20 мин |
| Системный аналитик — Middle | грейд | 13 / 10 | 20 мин |
| Data Scientist — Middle | грейд | 13 / 10 | 20 мин |
| Английский язык (CEFR) | навык | 22 / 15 | 20 мин |
| SQL | навык | 14 / 10 | 15 мин |
| Git | навык | 14 / 10 | 15 мин |
| Linux | навык | 14 / 10 | 15 мин |
| Docker | навык | 14 / 10 | 15 мин |
| Алгоритмы и структуры данных | навык | 14 / 10 | 15 мин |

Сами пакеты (`demo-tests.json`, `it-roles.json`, `skills.json`) лежат в
`backend/assessment-service/content/` и в git не попадают — см. ниже.

### Контент тестов

Вопросы и ответы хранятся **только в БД** assessment-service — в репозитории и
Docker-образе их нет. Кандидатские эндпоинты правильные ответы не возвращают.

Управляет контентом роль `admin` (при регистрации её выбрать нельзя):

```bash
docker compose exec auth-service python -m app.cli create-admin admin@benefit.ru
```

```
GET   /api/v1/assessments/admin/tests          список тестов (задачи, попытки)
GET   /api/v1/assessments/admin/tests/{id}     тест целиком, с ответами
POST  /api/v1/assessments/admin/tests          создать тест с банком задач
PUT   /api/v1/assessments/admin/tests/{id}     изменить (задачи — по key; убранные деактивируются)
PATCH /api/v1/assessments/admin/tests/{id}     {is_active} — опубликовать или снять
POST  /api/v1/assessments/admin/import         импорт пакета (?skip_existing=true)
GET   /api/v1/assessments/admin/export         выгрузка пакета (резервная копия)
```

Тест на навык в пакете задаётся так: `"kind": "skill"`, `"skill": "SQL"`,
`"levels": [{"id": "basic", "title": "Базовый", "min_percent": 40}, ...]`
(по возрастанию порога) — без `specialization` и `grade`.

Пакет тестов (`{"format_version": 1, "tests": [...]}`) можно импортировать и
из файла: положите его в `backend/assessment-service/content/` (папка в
`.gitignore` и `.dockerignore`, монтируется в контейнер) — при старте сервиса
новые тесты загрузятся автоматически. Вручную:
`docker compose exec assessment-service python -m app.cli import content/<файл>.json`.
Пакеты передавайте по защищённым каналам, не через git.

### Кабинет работодателя

**Профиль компании** (`employer-service`): название, ИНН (с проверкой
контрольных цифр), отрасль, описание, сайт, город, размер, стек, контакты.

```
GET|PUT /api/v1/employers/company                       свой профиль компании (+ verification)
POST    /api/v1/employers/company/verification          проверить компанию по открытым источникам
GET     /api/v1/employers/companies/{id}                профиль для кандидатов (verification.is_verified)
GET     /api/v1/employers/admin/companies?status=       модератор: очередь (по умолчанию registry_confirmed)
POST    /api/v1/employers/admin/companies/{id}/verification   модератор: {decision: verified|rejected, note}
```

**Проверка компании.** Статус выставляет только сервер:

| Статус | Что значит |
|---|---|
| `unverified` | не проверялась, или изменились ИНН либо сайт |
| `registry_confirmed` | компания действует по ЕГРЮЛ/ЕГРИП, связь с работодателем не доказана, ждёт модератора |
| `verified` | «Проверенный работодатель» (`verified_by`: `auto` или `moderator`) |
| `rejected` | ИНН нет в реестре, деятельность прекращена или отказал модератор |

ИНН проверяется по открытому поиску ФНС (egrul.nalog.ru, без ключа). Из
реестра берутся юридическое наименование, ОГРН, КПП, дата регистрации, регион
и руководитель (`verification.registry`).

Реестр подтверждает, что компания существует, но не то, что пользователь её
представляет. Поэтому `verified` выставляется автоматически, только если
выполнено всё:
- почта аккаунта корпоративная;
- почта на домене сайта компании;
- на сайте опубликован этот ИНН (главная, «контакты», «реквизиты»);
- ИНН не подтверждён за другим работодателем.

Иначе решение принимает модератор. Список `verification.checks` объясняет
работодателю, что пройдено и чего не хватает. Кандидатам видны только статус и
данные реестра.

Раз в час фоновая задача перепроверяет по реестру компании, проверенные больше
30 дней назад: ликвидация снимает статус. Запросы к сайту компании защищены от
SSRF: только http(s), стандартные порты, публичные адреса, не больше 2 МБ.

Значок есть в вакансиях (`company.is_verified`). В приглашениях, откликах и
процессах найма есть `company_id`: по нему фронт запрашивает профиль компании
с актуальным статусом.

**Потребность и подборка.** Работодатель описывает, кого ищет: специализация,
грейд, обязательный и желательный стек, чем занимается команда, формат,
бюджет. По потребности matching-service строит подборку:

```
GET|POST /api/v1/employers/needs                    потребности
GET|PUT|PATCH /api/v1/employers/needs/{id}          изменить / закрыть
GET  /api/v1/employers/needs/{id}/matches           подборка
```

Ответ подборки — рекомендованные **категории** (специализация + грейд +
подтверждён ли грейд, с числом кандидатов) и **кандидаты** с оценкой 0–100,
списком причин (`reasons`: «Стек: Python, PostgreSQL (2 из 3)», «Грейд
подтверждён тестированием (88%)», «Достижения ФСП: 2», «Профиль актуален…»)
и замечаниями (`warnings`: «Нет в стеке: Kafka», «Ожидания выше бюджета»).
Навыки нормализуются одним каталогом во всех сервисах («питон» = Python).

#### Подбор по вакансии и правила пересчёта

```
GET    /api/v1/employers/vacancies/{id}/matches?limit&offset&hide_contacted&refresh
GET    /api/v1/employers/vacancies/{id}/feedback
PUT    /api/v1/employers/vacancies/{id}/feedback/{candidate_id}   {verdict: like|dislike, comment}
DELETE /api/v1/employers/vacancies/{id}/feedback/{candidate_id}
```

**Потребность и вакансия.** Вакансия — самостоятельный объект подбора.
Критерии берутся из её полей:
- специализация и грейд;
- обязательные и желательные навыки;
- описание и обязанности (как ключевые слова);
- формат, город, бюджет;
- отрасль компании;
- настройки `matching`: строгие навыки, допуск по грейду, подтверждённый
  грейд, мин. опыт, жёсткий бюджет и формат.

Потребность (`need`) — шаблон и поиск до создания вакансии. При создании
вакансии с `need_id` из потребности один раз копируются пустые навыки,
настройки подбора и отметки «подходит / не подходит». Дальше критерии
принадлежат вакансии: правка потребности на неё не влияет.

**Правила пересчёта.** Сервер хранит подборку вакансии (до 100 лучших
кандидатов):

| Что изменилось | Что происходит |
|---|---|
| Требования вакансии (поля выше, отрасль компании) | `matching_version` + 1, `matching_state.requirements_changed: true`; при следующем запросе подборка пересчитывается (`recalculated: "criteria"`), в `changes` — кто добавился и кто выпал |
| Отметки «подходит / не подходит» | пересчёт (`"feedback"`), версия не меняется |
| Прошло 30 минут (кандидаты обновляют профили) | пересчёт (`"expired"`); `?refresh=true` — сразу (`"refresh"`) |
| Контакты (приглашён, отказался, отклонён) | применяются при каждом чтении, без пересчёта |
| Статус, даты вакансии | ничего |

Фронтенду: если в вакансии `matching_state.requirements_changed`, показанная
подборка устарела, и её нужно запросить заново. Архивная вакансия подбор не
отдаёт.

#### Алгоритм подбора

Подбор идёт в несколько этапов (код — `backend/matching-service/app/services/scoring.py`,
качество закреплено эталонными тестами `tests/test_ranking.py`):

1. **Отбор**: специализация или пересечение со стеком (включая близкие технологии);
   «не ищу работу» исключаются.
2. **Жёсткие фильтры** из потребности: `strict_skills` (все обязательные навыки,
   близкие не в счёт), `grade_tolerance` (допустимое отклонение грейда, по
   умолчанию ±1), `require_confirmed_grade`, `min_experience_months`,
   `hard_budget`, `strict_format`, город для офисной работы. Кандидаты,
   закрывающие меньше половины обязательного стека, отсеиваются. Скрываются
   кандидаты, которые отказали работодателю или чьи отклики он отклонил, и
   отмеченные «не подходит».
3. **Ранжирование** — оценка 0–100 с разбивкой (`breakdown`): обязательный
   стек 35, специализация 15, грейд 15, подтверждение грейда 10, близость
   опыта к задачам команды 8, активность и надёжность 7, желательный стек 5,
   ФСП 3, отрасль 2; штрафы — ожидания выше бюджета, давно неактивен, другой
   формат или город, стаж не соответствует грейду.
   * Навык засчитывается по глубине: уровень владения, сколько месяцев он был
     в стеке реальных мест работы и как давно использовался. Близкая
     технология (RabbitMQ вместо Kafka, Django вместо FastAPI…) — частичный зачёт.
   * Близость к задачам: ключевые слова из названия и описания потребности
     ищутся в опыте кандидата с учётом русской морфологии.
4. **Персонализация**: отметки работодателя по кандидатам
   (`PUT /api/v1/employers/needs/{id}/feedback/{candidate_id}` — `like`/`dislike`)
   поднимают похожих на одобренных и опускают похожих на отклонённых.
5. **Диагностика**: `excluded` — сколько кандидатов отсеяно и почему,
   `suggestions` — что ослабить, чтобы найти больше («Сделайте навык «Kafka»
   желательным — +3 кандидата»), категории с подсказкой («точное совпадение»,
   «грейд выше — сильнее, но дороже»), `contact_status` — был ли уже контакт.

Похожие кандидаты: `GET /api/v1/talent/candidates/{id}/similar`.

**Банк кандидатов** (`matching-service`) — вся база опубликованных профилей:

```
GET /api/v1/talent/candidates?specialization=&grade=&grade_status=confirmed
    &skills=python&skills=kafka&skills_mode=all|any&has_fsp=true&industry=&city=
    &work_format=&experience_min=&experience_max=&salary_max=
    &q=<полнотекстовый поиск>&active_only=&sort=relevance|skills|actuality|experience|fsp
```

В ответе — карточки (без контактов) и фасеты по категориям. Индекс
строится из ленты событий candidate-service (с учётом настроек
приватности) и обновляется в течение пары секунд после изменения профиля.

**Выход на контакт.** Приглашение с описанием предложения и зарплатой —
`POST /api/v1/invitations`; вакансия не обязательна. Компания подставляется
из профиля компании, а с `vacancy_id` — данные вакансии. Статусы — в
`GET /api/v1/invitations/sent`.

**Вакансии и отклики:**

```
GET|POST /api/v1/employers/vacancies[?status=]       свои вакансии (без фильтра — кроме архива)
PUT   /api/v1/employers/vacancies/{id}               изменить (архивную нельзя)
PATCH /api/v1/employers/vacancies/{id}               {status}: опубликовать / закрыть / в архив / восстановить
GET  /api/v1/vacancies[/{id}]                        каталог (?skill, salary_type, salary_min, …)
POST /api/v1/applications                            кандидат: откликнуться
GET  /api/v1/applications                            кандидат: мои отклики
GET  /api/v1/applications/received?vacancy_id=      работодатель: входящие отклики
POST /api/v1/applications/{id}/status                работодатель: viewed | invited | rejected
POST /api/v1/applications/{id}/withdraw              кандидат: отозвать
```

**Модель вакансии:**
- общее описание `description`;
- обязанности `responsibilities` — отдельными пунктами;
- `required_skills` — обязательные навыки;
- `optional_skills` — желательные навыки. Один навык не может быть сразу в
  обоих списках.
- зарплата `salary_from`/`salary_to`/`currency` с налоговым режимом
  `salary_type`: `gross` — до вычета НДФЛ, `net` — на руки. Режим попадает и
  в отклики и приглашения, где сумма выводится с пометкой «на руки» или «до
  вычета налогов».

Статусы и переходы:
- `draft → published` (публикация);
- `published → closed` (набор закрыт) и `closed → published` (открыть снова);
- `* → archived` (в архив);
- `archived → draft` (восстановить из архива).

Для публикации нужны хотя бы один обязательный навык и одна обязанность.
Недостающее перечислено в `publish_blockers`, а при попытке опубликовать
приходит ошибка 422 `vacancy_incomplete` с полями в `details`. Архив скрыт из
каталога и из списка по умолчанию и не редактируется. Даты `published_at`,
`closed_at` и `archived_at` фиксируются сервером. Поиск по навыку (`?skill=`)
ищет в обоих списках.

Отклик открывает работодателю контакты кандидата и создаёт переписку
(`source: "application"`); отказ или отзыв её закрывает.

## Тесты работодателей

Работодатель может составить свой тест и отправить его кандидату в
переписке. Такой тест виден только автору, не попадает в общий каталог и
**не подтверждает грейд** (категорию в профиле меняют только тесты платформы).

```
GET|POST /api/v1/assessments/employer/tests              свои тесты (с ответами)
GET|PUT|PATCH /api/v1/assessments/employer/tests/{id}    просмотр, изменение, архив
POST /api/v1/assessments/employer/tests/{id}/assignments отправить {conversation_id, due_at, message?}
GET  /api/v1/assessments/employer/assignments[/{id}]     результаты: ответы, баллы, время по задачам
POST /api/v1/assessments/employer/assignments/{id}/cancel
GET  /api/v1/assessments/assignments[/{id}]              кандидат: присланные тесты
POST /api/v1/assessments/assignments/{id}/start|decline  кандидат: начать (дальше /attempts/...) или отказаться
```

В переписке появляется карточка теста (`kind: "assessment"`, в `data` —
`assignment_id`), кандидат получает уведомление и письмо. Прохождение — тем же
механизмом с таймингом и баллами; если тест не начат до срока, он истекает.
Итог приходит в переписку и работодателю, а пройденный тест учитывается в
актуальности профиля (`employer_tests_completed`). Ответы кандидата
работодатель видит только после завершения теста.

## Приглашения и уведомления

```
POST /api/v1/invitations                       работодатель: пригласить {candidate_id, vacancy{title, company_name, salary_from, salary_to, …}, message}
GET  /api/v1/invitations/incoming              кандидат: входящие (?status=pending)
GET  /api/v1/invitations/sent                  работодатель: отправленные
POST /api/v1/invitations/{id}/accept|decline   кандидат: ответ {message?}
POST /api/v1/invitations/{id}/withdraw         работодатель: отозвать
GET  /api/v1/notifications                     уведомления текущего пользователя (+ /unread-count, /{id}/read, /read-all)
```

Пригласить можно только опубликованного кандидата; приглашение действует
14 дней. Каждый участник видит только свои приглашения (чужие — 404).
Приглашение и ответ на него приходят уведомлением в кабинет и письмом.

**Контакты кандидата** работодатель видит только после того, как кандидат
**принял его приглашение или сам откликнулся** на его вакансию
(`contact_access: "granted"` в профиле; до этого — `"hidden"`). Настройкой
приватности открыть контакты всем нельзя. В поиске и подборке контактов нет
вообще. Доступ сохраняется, даже если кандидат позже снимет профиль с
публикации.

## Процесс найма (applications-service)

Процесс найма — карточка «кандидат × вакансия» со своими этапами,
ответственным, интервью, офферами и историей. Создаётся автоматически, когда
кандидат **откликается** на вакансию или **принимает приглашение**.

Этапы по порядку: `new` → `screening` → `interview` → `assessment` → `offer` →
`hired`. Статус процесса: `active`, `hired`, `rejected`, `withdrawn`.
Работодатель переводит кандидата между этапами вперёд и назад. Назначение
интервью и отправка оффера сами сдвигают этап. В `hired` процесс переходит
только при **принятии оффера** кандидатом.

```
GET   /api/v1/hiring/dictionaries                              подписи этапов, статусов, типов событий
GET   /api/v1/hiring/team                                      работодатель: команда (ответственные, интервьюеры)
POST  /api/v1/hiring/team                                      {full_name, position?, email?}
PATCH /api/v1/hiring/team/{id}                                 изменить; is_active=false — убрать из команды
GET   /api/v1/hiring/processes                                 воронка (?status, stage, vacancy_id, responsible_id, candidate_id)
GET   /api/v1/hiring/processes/{id}                            карточка: интервью, офферы, полная история
POST  /api/v1/hiring/processes/{id}/stage                      {stage, comment?}
PUT   /api/v1/hiring/processes/{id}/responsible                {responsible_id | null}
POST  /api/v1/hiring/processes/{id}/comments                   внутренняя заметка {text}
POST  /api/v1/hiring/processes/{id}/reject                     {reason? (внутренняя), message? (кандидату)}
POST  /api/v1/hiring/processes/{id}/interviews                 {kind, scheduled_at, duration_minutes, format, location, interviewer_ids, note_for_candidate}
PATCH /api/v1/hiring/processes/{id}/interviews/{iid}           перенос / изменение
POST  /api/v1/hiring/processes/{id}/interviews/{iid}/cancel    {message?}
POST  /api/v1/hiring/processes/{id}/interviews/{iid}/result    {status: completed|no_show, rating 1–5, feedback}
POST  /api/v1/hiring/processes/{id}/offers                     {salary, currency, salary_type, start_date, …, expires_in_days}
POST  /api/v1/hiring/processes/{id}/offers/{oid}/withdraw
GET   /api/v1/hiring/my                                        кандидат: мои процессы
GET   /api/v1/hiring/my/{id}
POST  /api/v1/hiring/my/{id}/offers/{oid}/accept|decline       {message?}
POST  /api/v1/hiring/my/{id}/withdraw                          выйти из процесса {message?}
```

- **Ответственные и интервьюеры** — сотрудники из команды работодателя
  (`/hiring/team`). Это справочник людей, а не отдельные аккаунты: у компании
  по-прежнему один вход.
- **История** пишется по каждому действию: кто (`actor_role`: employer,
  candidate, system), когда, что изменилось (`data`) и комментарий.
  Кандидат видит только свою часть истории. Заметки, оценки интервью, причину
  отказа и смену ответственного он не видит.
- **Оффер:** ждать ответа может только один оффер. Без ответа он истекает
  через `expires_in_days`.
- **Завершение процесса.** При отказе, выходе кандидата или найме назначенные
  интервью отменяются, а ожидающий оффер отзывается. Отказ и выход закрывают
  переписку и отклик, с которого начался процесс. Смена статуса отклика
  (`invited`, `rejected`, `withdrawn`) тоже отражается в процессе.
- Интервью, оффер, ответ на оффер, отказ и выход приходят второй стороне
  уведомлением и письмом и дублируются системным сообщением в переписку.

## Переписка и регулярные задания (chat-service)

Диалог создаётся вместе с приглашением (первое сообщение — текст
приглашения). Писать могут только кандидат и работодатель этого
приглашения; после отказа или отзыва переписка становится только для чтения.

```
GET  /api/v1/chat/conversations[?invitation_id=]     диалоги (с непрочитанными)
GET  /api/v1/chat/conversations/{id}/messages?before= история (страницы по 50)
POST /api/v1/chat/conversations/{id}/messages        сообщение {text, attachment_ids, client_id}
POST /api/v1/chat/conversations/{id}/read            отметить прочитанным
POST /api/v1/chat/conversations/{id}/attachments     загрузить файл (до 20 МБ)
GET  /api/v1/chat/attachments/{id}                   скачать файл (только участникам)
WS   /api/v1/chat/ws                                 события в реальном времени
```

**WebSocket.** Первым сообщением — `{"type": "auth", "token": "<access token>"}`
(токен не передаётся в URL, чтобы не попадать в логи). Дальше клиент может
отправлять `message.send` (ответ — `message.ack`), `typing`, `read`, `ping`;
сервер присылает `message.created`, `conversation.read`, `typing`,
`task.updated`, `conversation.updated`. Протокол описан в
`backend/chat-service/app/api/v1/endpoints/ws.py`. События между экземплярами
сервиса расходятся через PostgreSQL `LISTEN/NOTIFY` и уходят только после
коммита. Если собеседник не в сети, он получит уведомление и письмо
(не чаще раза в час на диалог).

**Файлы**: белый список расширений (документы, изображения, архивы, код),
исполняемые файлы отклоняются; отдаются только как вложение с `nosniff`.
Хранятся в томе `chat_files` (за интерфейсом `FileStorage` — можно заменить
на S3-совместимое хранилище).

**Регулярные задания.** Работодатель выдаёт задание в переписке:

```
POST /api/v1/chat/conversations/{id}/tasks   {title, description, due_at, attachment_ids, recurrence_days?}
POST /api/v1/chat/tasks/{id}/submit          кандидат: {response_type: solution|approach, text, attachment_ids}
POST /api/v1/chat/tasks/{id}/review          работодатель: {result: passed|failed, score?, feedback?}
POST /api/v1/chat/tasks/{id}/cancel | stop-recurrence
GET  /api/v1/chat/tasks                      мои задания
```

Кандидат решает задачу или предлагает подход. Планировщик напоминает о
сроке за сутки, просрочивает задания без ответа и снова выдаёт регулярные
задания (`recurrence_days`). Результаты попадают в candidate-service и
формируют **актуальность профиля** (`actuality` в профиле, видна работодателю):
`active` — активность за 30 дней, `recent` — за 90, `stale` — давно; плюс
статистика заданий за 180 дней (выдано, сдано, принято, просрочено).

## Тесты

```bash
# auth-service: нужен запущенный auth-db (docker compose up -d auth-db)
cd backend/auth-service && pip install -e '.[dev]' && pytest
```

Сервисы с БД тестируются на своих Postgres из docker-compose (`auth-db`,
`candidate-db`, `assessment-db`, `applications-db`, `notification-db`). Для
сервисов на общей библиотеке сначала: `pip install -e ../libs/benefit-common`.

candidate-service: для экспорта PDF нужен Pango (в Docker уже есть; на macOS: `brew install pango` и запуск
с `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`). Остальные сервисы тестируются
так же, без внешних зависимостей.
