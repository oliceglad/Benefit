"""Настройка логирования приложения."""

import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO") -> None:
    """Настраивает корневой логгер с выводом в stdout."""
    logging.basicConfig(
        level=level.upper(),
        format=LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )
