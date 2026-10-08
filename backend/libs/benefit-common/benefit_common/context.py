"""Контекст текущего запроса: сквозной ID и имя сервиса."""

from contextvars import ContextVar

REQUEST_ID_HEADER = "X-Request-ID"

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
service_name_var: ContextVar[str] = ContextVar("service_name", default="unknown")

# Названия сервисов для сообщений пользователю.
SERVICE_TITLES = {
    "gateway": "API-шлюз",
    "core": "основной сервис",
    "auth-service": "сервис авторизации",
    "candidate-service": "сервис профилей кандидатов",
    "assessment-service": "сервис тестирования",
    "applications-service": "сервис приглашений и откликов",
    "notification-service": "сервис уведомлений",
    "mail-service": "почтовый сервис",
    "chat-service": "сервис переписки",
    "employer-service": "сервис работодателей",
    "matching-service": "сервис подбора кандидатов",
}


def service_title(name: str) -> str:
    return SERVICE_TITLES.get(name, f"сервис {name}")


def current_request_id() -> str | None:
    return request_id_var.get()


def current_service() -> str:
    return service_name_var.get()
