"""Исходящие события для других сервисов (transactional outbox)."""

from benefit_common.outbox import OutboxMessageMixin

from app.db.base import Base


class OutboxMessage(OutboxMessageMixin, Base):
    """Например, удаление аккаунта: каждый сервис удаляет свои данные."""

    __tablename__ = "outbox_messages"
