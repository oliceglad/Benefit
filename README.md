# Benefit

Сервис подбора кандидатов на вакансии.

## Стек

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic
- **БД:** PostgreSQL 17 (FTS, pg_trgm, pgvector)
- **Frontend:** в разработке

## Структура

```
benefit/
├── backend/            # FastAPI-приложение
├── frontend/           # клиентское приложение (в разработке)
├── docker-compose.yml
└── .env.example
```

## Запуск

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

Миграции применяются автоматически при старте контейнера backend.
