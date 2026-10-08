"""Схемы согласий на обработку и публикацию данных."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ConsentType(StrEnum):
    # Согласие на обработку персональных данных (152-ФЗ).
    PERSONAL_DATA = "personal_data"
    # Согласие на публикацию профиля для работодателей.
    PUBLICATION = "publication"


class ConsentStatus(BaseModel):
    type: ConsentType
    title: str
    document_url: str
    required_version: str
    granted: bool = Field(description="Действует согласие на актуальную версию")
    granted_version: str | None
    granted_at: datetime | None


class ConsentGrant(BaseModel):
    type: ConsentType
    version: str = Field(
        description="Версия документа, с которой согласился пользователь"
    )
