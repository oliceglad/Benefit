#!/usr/bin/env bash
# Деплой Benefit (фронтенд + бэкенд) на сервер. Запускается на сервере из
# каталога проекта: CI копирует код через rsync и вызывает скрипт по SSH.
#
#   PUBLIC_HOST=<адрес сервера> bash .github/scripts/deploy.sh [--detached]
#
# --detached: вывод — в deploy.log, код выхода — в deploy.status. CI запускает
# так, чтобы обрыв SSH во время долгой сборки не убивал деплой, и забирает
# лог короткими подключениями.
#
# Идемпотентен: при первом запуске ставит Docker и создаёт .env со случайными
# секретами; дальше .env не трогает (пароли БД менять после создания томов
# нельзя — базы перестанут пускать сервисы).
#
# Снаружи открыт только фронтенд (порт 80): он отдаёт SPA и проксирует
# /api, /docs, /.well-known на шлюз, который слушает лишь 127.0.0.1:8000.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$APP_DIR"

if [ "${1:-}" = "--detached" ]; then
    exec >deploy.log 2>&1
    trap 'echo $? > "$APP_DIR/deploy.status"' EXIT
fi

PUBLIC_HOST="${PUBLIC_HOST:?укажите PUBLIC_HOST — адрес сервера}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-600}"

log() { printf '\n▶ %s\n' "$*"; }

# Два деплоя одновременно не идут.
exec 9>/var/lock/benefit-deploy.lock
flock -n 9 || { echo "Деплой уже выполняется"; exit 1; }

# --- Память -----------------------------------------------------------------
# Сборка дюжины образов и стек из ~25 контейнеров легко съедают память
# небольшого сервера; без swap ядро убивает процессы (OOM), вплоть до sshd.
if [ "$(swapon --noheadings | wc -l)" -eq 0 ] && [ ! -f /swapfile ]; then
    log "Создаю swap 4 ГБ (/swapfile)"
    fallocate -l 4G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=4096
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
free -h

# --- Docker -----------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    log "Устанавливаю Docker"
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
fi
docker compose version

# --- .env -------------------------------------------------------------------
secret() { openssl rand -hex 24; }

set_var() {
    local key="$1" value="$2"
    if grep -q "^${key}=" .env; then
        # Разделитель | — в значениях бывают / и :.
        sed -i "s|^${key}=.*|${key}=${value}|" .env
    else
        printf '%s=%s\n' "$key" "$value" >> .env
    fi
}

if [ ! -f .env ]; then
    log "Создаю .env (секреты генерируются один раз)"
    cp .env.example .env
    chmod 600 .env
    origin="http://${PUBLIC_HOST}"
    # Сервер без HTTPS: production-режим требует Secure-cookie и https-origins,
    # поэтому APP_ENV=local, но без отладки и с настоящими секретами.
    set_var APP_ENV local
    set_var DEBUG false
    set_var FRONTEND_PORT 80
    set_var GATEWAY_PORT 127.0.0.1:8000
    set_var AUTH_PUBLIC_URL "$origin"
    set_var FRONTEND_URL "$origin"
    set_var CORS_ORIGINS "[\"${origin}\"]"
    set_var TRUSTED_ORIGINS "[\"${origin}\"]"
    set_var COOKIE_SECURE false
    set_var AUTH_SECRET_KEY "$(secret)"
    set_var INTERNAL_API_TOKEN "$(secret)"
    for key in POSTGRES AUTH_DB CANDIDATE_DB ASSESSMENT_DB APPLICATIONS_DB \
        NOTIFICATION_DB CHAT_DB EMPLOYER_DB MATCHING_DB; do
        set_var "${key}_PASSWORD" "$(secret)"
    done
    set_var GRAFANA_ADMIN_PASSWORD "$(secret)"
    set_var KEYCLOAK_ADMIN_PASSWORD "$(secret)"
fi

# Пакеты тестов в git не хранятся (кладутся на сервер вручную), но каталог
# монтируется в assessment-service и должен существовать.
mkdir -p backend/assessment-service/content

# --- Запуск -----------------------------------------------------------------
log "Сборка и запуск (ревизия $(cat REVISION 2>/dev/null || echo '?'))"
# Образы собираются по одному: параллельная сборка всех сразу
# перегружает небольшой сервер. Общие слои берутся из кэша.
for service in $(docker compose config --services); do
    docker compose build "$service"
done
docker compose up -d --remove-orphans

log "Жду, пока контейнеры станут healthy (до ${HEALTH_TIMEOUT} с)"
deadline=$((SECONDS + HEALTH_TIMEOUT))
while :; do
    # Упавшие контейнеры и контейнеры с healthcheck, которые ещё не healthy.
    pending=$(docker compose ps -a --format '{{.Service}} {{.State}} {{.Health}}' \
        | awk '$2 != "running" || ($3 != "" && $3 != "healthy")')
    [ -z "$pending" ] && break
    if [ "$SECONDS" -ge "$deadline" ]; then
        echo "Не дождался готовности:"
        echo "$pending"
        for service in $(echo "$pending" | awk '{print $1}'); do
            echo "--- логи $service"
            docker compose logs --tail 40 "$service"
        done
        exit 1
    fi
    sleep 5
done

log "Проверка снаружи: фронтенд → шлюз → сервисы"
port=$(grep -E '^FRONTEND_PORT=' .env | cut -d= -f2)
base="http://127.0.0.1:${port:-80}"
curl -fsS -o /dev/null "$base/"
status=$(curl -fsS "$base/api/v1/status")
echo "$status"
echo "$status" | grep -q '^{"status":"ok"' || { echo "Не все сервисы в статусе ok"; exit 1; }

# Старые образы после пересборки занимают место на диске.
docker image prune -f >/dev/null
log "Готово: http://${PUBLIC_HOST}/ (Swagger: http://${PUBLIC_HOST}/docs)"
