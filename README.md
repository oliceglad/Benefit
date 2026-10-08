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
│   ├── applications-service/# приглашения работодателей (позже — отклики)
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
| ФСП ID (mock)             | http://localhost:8003                   |
| Keycloak (admin/admin)    | http://localhost:8080                   |

Маршрутизация шлюза: `/api/v1/auth/*`, `/api/v1/users/*`, `/.well-known/*` →
auth-service, `/api/v1/candidates/*` → candidate-service, `/api/v1/assessments/*` →
assessment-service, `/api/v1/invitations*` → applications-service,
`/api/v1/notifications*` → notification-service, `/api/v1/chat/*` (включая
WebSocket `/api/v1/chat/ws`) → chat-service, `/api/v1/employers/*` и
`/api/v1/vacancies*` → employer-service, `/api/v1/talent/*` → matching-service,
`/api/v1/applications*` → applications-service, всё остальное → core.
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
GET  /api/v1/assessments/status                     подтверждённая категория, кулдауны
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
- Примеры тестов: «Python Backend — Middle» (12 задач, 8 в попытке, 20 минут)
  и «QA Automation — Junior» (10 задач, 8 в попытке, 15 минут).

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
GET|PUT /api/v1/employers/company            свой профиль компании
GET     /api/v1/employers/companies/{id}     профиль компании для кандидатов
```

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
GET|POST /api/v1/employers/vacancies                 свои вакансии (черновик)
PUT|PATCH /api/v1/employers/vacancies/{id}           изменить / опубликовать / закрыть
GET  /api/v1/vacancies[/{id}]                        каталог опубликованных вакансий
POST /api/v1/applications                            кандидат: откликнуться
GET  /api/v1/applications                            кандидат: мои отклики
GET  /api/v1/applications/received?vacancy_id=      работодатель: входящие отклики
POST /api/v1/applications/{id}/status                работодатель: viewed | invited | rejected
POST /api/v1/applications/{id}/withdraw              кандидат: отозвать
```

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
