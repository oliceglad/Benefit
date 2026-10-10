"""Схемы откликов на вакансии."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import ApplicationStatus


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vacancy_id: uuid.UUID
    cover_letter: str | None = Field(default=None, max_length=4000)


class ApplicationStatusUpdate(BaseModel):
    """Работодатель: просмотрен, приглашение на собеседование или отказ."""

    status: Literal["viewed", "invited", "rejected"]
    message: str | None = Field(default=None, max_length=2000)


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vacancy_id: uuid.UUID
    employer_id: uuid.UUID
    candidate_id: uuid.UUID
    vacancy_title: str
    company_name: str
    # Профиль компании со статусом проверки (employer-service).
    company_id: uuid.UUID | None
    salary_from: int | None
    salary_to: int | None
    currency: str
    # gross — до вычета НДФЛ, net — на руки.
    salary_type: Literal["gross", "net"]
    cover_letter: str | None
    status: ApplicationStatus
    employer_message: str | None
    status_changed_at: datetime | None
    created_at: datetime
