#!/bin/sh
set -e

echo "Applying database migrations..."
alembic upgrade head

# Пакеты тестов монтируются в контейнер извне (в образ и git не попадают).
# Импортируются только новые тесты: правки через админский API не теряются.
if [ -d "${ASSESSMENT_CONTENT_DIR:-/app/content}" ]; then
    python -m app.cli import "${ASSESSMENT_CONTENT_DIR:-/app/content}" --skip-existing
fi

exec "$@"
