"""Привязка пользователя к аккаунту во внешнем провайдере (Keycloak, ФСП ID)."""

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ExternalIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_identities"
    __table_args__ = (UniqueConstraint("provider", "subject"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    # Claim ``sub`` из ID-токена провайдера.
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))

    user: Mapped["User"] = relationship(back_populates="identities")  # noqa: F821
