"""Схемы уведомлений."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NotificationCreate(BaseModel):
    """Запрос от другого сервиса на уведомление пользователя."""

    user_id: uuid.UUID
    type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    link: str | None = Field(default=None, max_length=500, pattern=r"^/")
    data: dict[str, Any] = Field(default_factory=dict)
    # Продублировать на почту.
    email: bool = True
    dedup_key: str | None = Field(default=None, max_length=200)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    title: str
    body: str
    link: str | None
    data: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationResponse]
    unread_count: int
