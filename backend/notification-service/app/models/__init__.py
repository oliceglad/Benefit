"""ORM-модели notification-service."""

import uuid
from datetime import datetime
from typing import Any

from benefit_common.outbox import OutboxMessageMixin
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    # Тип для фильтрации и иконок на фронтенде: invitation.received и т. п.
    type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    # Путь на фронтенде (например, /invitations/<id>).
    link: Mapped[str | None] = mapped_column(String(500))
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Ключ идемпотентности: повторная доставка от другого сервиса
    # не создаёт дубль уведомления.
    dedup_key: Mapped[str | None] = mapped_column(String(200), unique=True)


class EmailDelivery(OutboxMessageMixin, Base):
    """Очередь писем: доставляется фоново с повторными попытками."""

    __tablename__ = "email_deliveries"


__all__ = ["Base", "EmailDelivery", "Notification"]
