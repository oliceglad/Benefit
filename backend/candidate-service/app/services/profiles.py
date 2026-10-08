"""Профиль кандидата: создание, редактирование, публикация, представления."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import Principal
from app.models.candidate import CandidateProfile, ProfileStatus
from app.repositories.candidates import ProfileRepository
from app.schemas.profile import (
    Completeness,
    FspAchievementResponse,
    FspInfo,
    PrivacySettings,
    ProfileResponse,
    ProfileUpdate,
    PublicProfileResponse,
    age_on,
)
from app.services.completeness import evaluate
from app.services.consents import ConsentService
from app.services.events import EventType, record_event

# Поля, которые хранятся в JSONB и сериализуются в JSON-совместимый вид.
JSON_FIELDS = {
    "links",
    "roles",
    "skills",
    "soft_skills",
    "languages",
    "experience",
    "education",
    "courses",
    "projects",
    "employment_types",
    "work_formats",
    "privacy",
}

HIDDEN_COMPANY = "Компания скрыта"


def _profile_not_found() -> AppError:
    return AppError(
        "Профиль не найден",
        code="profile_not_found",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def total_experience_months(experience: list[dict[str, Any]], today: date) -> int:
    """Суммарный стаж без двойного учёта пересекающихся мест работы."""
    intervals = []
    for item in experience:
        start = date.fromisoformat(item["start_date"])
        end = date.fromisoformat(item["end_date"]) if item.get("end_date") else today
        start_m = start.year * 12 + start.month
        end_m = end.year * 12 + end.month + 1  # месяц окончания включительно
        if end_m > start_m:
            intervals.append((start_m, end_m))
    total, current_end = 0, None
    for start_m, end_m in sorted(intervals):
        if current_end is not None and start_m < current_end:
            if end_m > current_end:
                total += end_m - current_end
                current_end = end_m
        else:
            total += end_m - start_m
            current_end = end_m
    return total


def privacy_of(profile: CandidateProfile) -> PrivacySettings:
    return PrivacySettings.model_validate(profile.privacy or {})


def matching_snapshot(profile: CandidateProfile) -> dict[str, Any]:
    """Данные для сервисов подбора и тестирования (события, внутренний API)."""
    return {
        "status": profile.status,
        "headline": profile.headline,
        "grade": profile.grade,
        "verified_grade": profile.verified_grade,
        "roles": profile.roles,
        "skills": profile.skills,
        "soft_skills": profile.soft_skills,
        "languages": profile.languages,
        "total_experience_months": total_experience_months(
            profile.experience, date.today()
        ),
        "city": profile.city,
        "relocation_ready": profile.relocation_ready,
        "salary_from": profile.salary_from,
        "salary_currency": profile.salary_currency,
        "employment_types": profile.employment_types,
        "work_formats": profile.work_formats,
        "job_search_status": profile.job_search_status,
    }


class ProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.profiles = ProfileRepository(session)
        self.consents = ConsentService(session)

    async def get(self, user_id: uuid.UUID) -> CandidateProfile:
        profile = await self.profiles.get(user_id)
        if profile is None:
            raise _profile_not_found()
        return profile

    async def get_or_create(self, principal: Principal) -> CandidateProfile:
        """Профиль создаётся черновиком при первом входе в личный кабинет."""
        profile = await self.profiles.get(principal.id)
        if profile is not None:
            return profile
        profile = CandidateProfile(
            user_id=principal.id,
            contact_email=principal.email or None,
            privacy=PrivacySettings().model_dump(),
        )
        self.session.add(profile)
        await self.session.commit()
        return await self._reload(profile)

    async def _reload(self, profile: CandidateProfile) -> CandidateProfile:
        """Перечитывает поля, вычисленные БД (``updated_at`` и т. п.)."""
        await self.session.refresh(profile)
        return profile

    async def completeness(self, profile: CandidateProfile) -> Completeness:
        return evaluate(
            profile,
            has_photo=await self.profiles.has_photo(profile.user_id),
            has_consents=await self.consents.has_all(profile.user_id),
        )

    async def update(
        self, profile: CandidateProfile, data: ProfileUpdate
    ) -> CandidateProfile:
        values = data.model_dump(exclude_unset=True)
        json_values = data.model_dump(mode="json", exclude_unset=True)
        for field in values:
            value = json_values[field] if field in JSON_FIELDS else values[field]
            setattr(profile, field, value)

        if profile.status == ProfileStatus.PUBLISHED:
            completeness = await self.completeness(profile)
            if not completeness.can_publish:
                raise AppError(
                    "Опубликованный профиль должен содержать обязательные поля: "
                    + ", ".join(completeness.missing_required),
                    code="profile_incomplete",
                    status_code=422,
                )
            record_event(
                self.session,
                profile.user_id,
                EventType.PROFILE_UPDATED,
                matching_snapshot(profile),
            )
        await self.session.commit()
        return await self._reload(profile)

    async def publish(self, profile: CandidateProfile) -> CandidateProfile:
        completeness = await self.completeness(profile)
        if not completeness.can_publish:
            raise AppError(
                "Заполните обязательные поля и дайте согласия: "
                + ", ".join(completeness.missing_required),
                code="profile_incomplete",
                status_code=422,
            )
        if profile.status != ProfileStatus.PUBLISHED:
            profile.status = ProfileStatus.PUBLISHED
            profile.published_at = datetime.now(UTC)
            record_event(
                self.session,
                profile.user_id,
                EventType.PROFILE_PUBLISHED,
                matching_snapshot(profile),
            )
            await self.session.commit()
        return await self._reload(profile)

    async def unpublish(
        self, profile: CandidateProfile, reason: str = "by_user"
    ) -> CandidateProfile:
        if profile.status == ProfileStatus.PUBLISHED:
            profile.status = ProfileStatus.DRAFT
            record_event(
                self.session,
                profile.user_id,
                EventType.PROFILE_UNPUBLISHED,
                {"reason": reason},
            )
            await self.session.commit()
        return await self._reload(profile)

    async def delete(self, profile: CandidateProfile) -> None:
        """Удаление профиля по запросу пользователя. Журнал согласий
        сохраняется (с отзывом), он нужен как подтверждение законности
        обработки данных в прошлом."""
        user_id = profile.user_id
        await self.session.delete(profile)
        for consent in await self.consents.repository.active(user_id):
            consent.revoked_at = datetime.now(UTC)
        record_event(self.session, user_id, EventType.PROFILE_DELETED)
        await self.session.commit()

    async def to_response(self, profile: CandidateProfile) -> ProfileResponse:
        achievements = await self.profiles.achievements(profile.user_id)
        today = date.today()
        return ProfileResponse.model_validate(
            {
                **self._common(profile, today),
                "user_id": profile.user_id,
                "status": profile.status,
                "published_at": profile.published_at,
                "birth_date": profile.birth_date,
                "age": age_on(profile.birth_date, today)
                if profile.birth_date
                else None,
                "phone": profile.phone,
                "contact_email": profile.contact_email,
                "telegram": profile.telegram,
                "salary_from": profile.salary_from,
                "salary_currency": profile.salary_currency,
                "privacy": privacy_of(profile),
                "has_photo": await self.profiles.has_photo(profile.user_id),
                "fsp": FspInfo(
                    linked=profile.fsp_participant_id is not None,
                    participant_id=profile.fsp_participant_id,
                    synced_at=profile.fsp_synced_at,
                    achievements=[
                        FspAchievementResponse.model_validate(a) for a in achievements
                    ],
                ),
                "completeness": await self.completeness(profile),
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
            }
        )

    async def public_view(self, user_id: uuid.UUID) -> PublicProfileResponse:
        """Профиль для работодателя: только опубликованный и с учётом
        настроек приватности."""
        profile = await self.profiles.get(user_id)
        if profile is None or profile.status != ProfileStatus.PUBLISHED:
            raise _profile_not_found()
        privacy = privacy_of(profile)
        today = date.today()
        common = self._common(profile, today)
        if privacy.hide_current_company:
            common["experience"] = [
                {**item, "company": HIDDEN_COMPANY}
                if not item.get("end_date")
                else item
                for item in common["experience"]
            ]
        achievements = (
            await self.profiles.achievements(user_id)
            if privacy.show_fsp_achievements
            else []
        )
        show_age = privacy.show_birth_date and profile.birth_date
        return PublicProfileResponse.model_validate(
            {
                **common,
                "user_id": profile.user_id,
                "published_at": profile.published_at,
                "age": age_on(profile.birth_date, today) if show_age else None,
                "phone": profile.phone if privacy.show_contacts else None,
                "contact_email": (
                    profile.contact_email if privacy.show_contacts else None
                ),
                "telegram": profile.telegram if privacy.show_contacts else None,
                "salary_from": profile.salary_from if privacy.show_salary else None,
                "salary_currency": (
                    profile.salary_currency if privacy.show_salary else None
                ),
                "has_photo": privacy.show_photo
                and await self.profiles.has_photo(user_id),
                "fsp_achievements": [
                    FspAchievementResponse.model_validate(a) for a in achievements
                ],
            }
        )

    async def revoke_consent_effects(self, profile: CandidateProfile | None) -> None:
        """Без действующих согласий профиль снимается с публикации."""
        if profile is not None and profile.status == ProfileStatus.PUBLISHED:
            await self.unpublish(profile, reason="consent_revoked")

    @staticmethod
    def _common(profile: CandidateProfile, today: date) -> dict[str, Any]:
        return {
            "last_name": profile.last_name,
            "first_name": profile.first_name,
            "middle_name": profile.middle_name,
            "city": profile.city,
            "relocation_ready": profile.relocation_ready,
            "headline": profile.headline,
            "about": profile.about,
            "grade": profile.grade,
            "verified_grade": profile.verified_grade,
            "grade_verified_at": profile.grade_verified_at,
            "roles": profile.roles,
            "skills": profile.skills,
            "soft_skills": profile.soft_skills,
            "languages": profile.languages,
            "experience": profile.experience,
            "education": profile.education,
            "courses": profile.courses,
            "projects": profile.projects,
            "links": profile.links,
            "employment_types": profile.employment_types,
            "work_formats": profile.work_formats,
            "job_search_status": profile.job_search_status,
            "total_experience_months": total_experience_months(
                profile.experience, today
            ),
        }
