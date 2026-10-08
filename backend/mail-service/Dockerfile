# Контекст сборки — папка backend (см. docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY libs/benefit-common /opt/libs/benefit-common
RUN pip install /opt/libs/benefit-common

COPY mail-service/pyproject.toml ./
COPY mail-service/app/__init__.py ./app/__init__.py
RUN pip install .

COPY mail-service/ .
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
