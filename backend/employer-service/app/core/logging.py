"""Логирование: в каждой записи — имя сервиса и сквозной ID запроса."""

from benefit_common.observability import configure_logging

SERVICE_NAME = "employer-service"


def setup_logging(level: str = "INFO") -> None:
    configure_logging(level, SERVICE_NAME)
