"""Базовый декларативный класс для всех ORM-моделей."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Единые правила именования ограничений — Alembic генерирует
# стабильные и предсказуемые имена индексов и ключей.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Базовый класс ORM-моделей."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
