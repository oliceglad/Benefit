# Сборка SPA и раздача через nginx. nginx же проксирует API на шлюз:
# браузер ходит на тот же origin, CORS и отдельный домен для API не нужны.

FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
# Пусто — API на том же origin (через nginx ниже).
ARG VITE_API_BASE_URL=""
ARG VITE_LEGAL_OPERATOR_NAME=""
ARG VITE_LEGAL_OPERATOR_ADDRESS=""
ARG VITE_LEGAL_CONTACT_EMAIL=""
RUN pnpm build

FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
