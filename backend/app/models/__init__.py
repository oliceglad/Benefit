"""ORM-модели предметной области.

Каждую новую модель нужно импортировать здесь, чтобы она попала
в ``Base.metadata`` и была видна Alembic при autogenerate.
"""

from app.db.base import Base

__all__ = ["Base"]
