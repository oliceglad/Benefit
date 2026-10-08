"""Подборка кандидатов: критерии из потребности + отметки работодателя +
история контактов → matching-service."""

import logging
import uuid
from typing import Any, Protocol

from benefit_common.errors import AppError
from benefit_common.internal import InternalClient, raise_for_client_error

from app.core.config import settings
from app.models import FeedbackVerdict, HiringNeed, NeedFeedback

logger = logging.getLogger(__name__)


class Matcher(Protocol):
    async def match(self, criteria: dict[str, Any]) -> dict[str, Any]: ...


class ContactDirectory(Protocol):
    async def contacts(self, employer_id: uuid.UUID) -> dict[str, str]:
        """С кем уже был контакт: ``{candidate_id: статус}``."""
        ...


def need_criteria(
    need: HiringNeed,
    feedback: list[NeedFeedback] | None = None,
    contacted: dict[str, str] | None = None,
) -> dict[str, Any]:
    feedback = feedback or []
    return {
        "specialization": need.specialization,
        "grade": need.grade,
        "required_skills": need.required_skills,
        "optional_skills": need.optional_skills,
        "title": need.title,
        "team_description": need.team_description,
        "industry": need.company.industry,
        "work_formats": need.work_formats,
        "city": need.city,
        "salary_to": need.salary_to,
        "currency": need.currency,
        "require_confirmed_grade": need.require_confirmed_grade,
        "strict_skills": need.strict_skills,
        "grade_tolerance": need.grade_tolerance,
        "min_experience_months": need.min_experience_months,
        "hard_budget": need.hard_budget,
        "strict_format": need.strict_format,
        "liked_ids": [
            str(f.candidate_id) for f in feedback if f.verdict == FeedbackVerdict.LIKE
        ],
        "disliked_ids": [
            str(f.candidate_id)
            for f in feedback
            if f.verdict == FeedbackVerdict.DISLIKE
        ],
        "contacted": contacted or {},
    }


class MatchingClient:
    def __init__(self) -> None:
        self.client = InternalClient(settings.matching_service_url, service="matching")

    async def match(self, criteria: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.post("/internal/v1/match", json=criteria)
        raise_for_client_error(response)
        return response.json()


class ApplicationsClient:
    def __init__(self) -> None:
        self.client = InternalClient(
            settings.applications_service_url, service="applications"
        )

    async def contacts(self, employer_id: uuid.UUID) -> dict[str, str]:
        try:
            response = await self.client.get(
                f"/internal/v1/employers/{employer_id}/contacts"
            )
            raise_for_client_error(response)
        except AppError:
            # Подборка полезна и без пометок о контактах.
            logger.warning("Contacts unavailable, matching without them")
            return {}
        return response.json()


def get_matcher() -> Matcher:
    return MatchingClient()


def get_contacts() -> ContactDirectory:
    return ApplicationsClient()
