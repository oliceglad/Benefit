"""Текущее время. Вынесено отдельно, чтобы тесты могли «перематывать» время."""

from datetime import UTC, datetime


def now() -> datetime:
    return datetime.now(UTC)
