"""Схемы приглашений."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.models import InvitationStatus

Text200 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


def check_salary[M: BaseModel](model: M) -> M:
    low, high = getattr(model, "salary_from", None), getattr(model, "salary_to", None)
    if low is not None and high is not None and low > high:
        raise ValueError("Зарплата «от» больше, чем «до»")
    return model


class Vacancy(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vacancy_id: str | None = Field(default=None, max_length=64)
    title: Text200
    company_name: Text200
    salary_from: int | None = Field(default=None, ge=0, le=100_000_000)
    salary_to: int | None = Field(default=None, ge=0, le=100_000_000)
    currency: str = Field(default="RUB", pattern=r"^[A-Z]{3}$")
    work_format: str | None = Field(default=None, pattern=r"^(office|remote|hybrid)$")
    city: str | None = Field(default=None, max_length=100)

    _check_salary = model_validator(mode="after")(check_salary)


class Offer(BaseModel):
    """Предложение в приглашении. Привязка к вакансии необязательна:
    с ``vacancy_id`` недостающие поля берутся из вакансии, а название
    компании — из профиля компании работодателя."""

    model_config = ConfigDict(extra="forbid")

    vacancy_id: uuid.UUID | None = None
    title: Text200 | None = None
    company_name: Text200 | None = None
    salary_from: int | None = Field(default=None, ge=0, le=100_000_000)
    salary_to: int | None = Field(default=None, ge=0, le=100_000_000)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    work_format: str | None = Field(default=None, pattern=r"^(office|remote|hybrid)$")
    city: str | None = Field(default=None, max_length=100)

    _check_salary = model_validator(mode="after")(check_salary)


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: uuid.UUID
    vacancy: Offer
    message: str | None = Field(default=None, max_length=2000)


class InvitationReply(BaseModel):
    message: str | None = Field(default=None, max_length=2000)


class InvitationResponse(BaseModel):
    id: uuid.UUID
    status: InvitationStatus
    candidate_id: uuid.UUID
    employer_id: uuid.UUID
    vacancy: Vacancy
    message: str | None
    response_message: str | None
    created_at: datetime
    responded_at: datetime | None
    expires_at: datetime
