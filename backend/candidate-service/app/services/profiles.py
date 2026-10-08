"""Профиль кандидата: создание, редактирование, публикация, представления."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from benefit_common.errors import AppError
from benefit_common.security import Principal
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dictionaries import GRADE_ORDER, Grade
from app.models.candidate import CandidateProfile, ProfileStatus
from app.repositories.candidates import ProfileRepository
from app.schemas.consent import ConsentType
from app.schemas.profile import (
    Actuality,
    ActualityStatus,
    Category,
    Completeness,
    ContactAccess,
    FspAchievementResponse,
    FspInfo,
    GradeStatus,
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

# Актуальность профиля: «активен» — активность за 30 дней, «недавно» — за 90.
ACTIVE_DAYS = 30
RECENT_DAYS = 90
ACTIVITY_WINDOW_DAYS = 180


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


def category_of(profile: CandidateProfile) -> Category:
    claimed = Grade(profile.grade) if profile.grade else None
    verified = Grade(profile.verified_grade) if profile.verified_grade else None
    if verified and (claimed is None or GRADE_ORDER[verified] >= GRADE_ORDER[claimed]):
        details = profile.verification or {}
        return Category(
            industry=profile.industry,
            specialization=profile.verified_specialization,
            grade=verified,
            grade_status=GradeStatus.CONFIRMED,
            verified_at=profile.grade_verified_at,
            test_title=details.get("test_title"),
            percent=details.get("percent"),
        )
    return Category(
        industry=profile.industry,
        specialization=profile.roles[0] if profile.roles else None,
        grade=claimed,
        grade_status=GradeStatus.NOT_CONFIRMED,
    )


def privacy_of(profile: CandidateProfile) -> PrivacySettings:
    return PrivacySettings.model_validate(profile.privacy or {})


def matching_snapshot(profile: CandidateProfile) -> dict[str, Any]:
    """Данные для сервисов подбора и тестирования (события, внутренний API)."""
    return {
        "status": profile.status,
        "headline": profile.headline,
        "grade": profile.grade,
        "verified_grade": profile.verified_grade,
        "industry": profile.industry,
        "category": category_of(profile).model_dump(mode="json"),
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

    async def actuality(self, profile: CandidateProfile) -> Actuality:
        current = datetime.now(UTC)
        counts, last_task = await self.profiles.activity_stats(
            profile.user_id, current - timedelta(days=ACTIVITY_WINDOW_DAYS)
        )
        moments = [profile.updated_at, profile.grade_verified_at, last_task]
        last_active = max(m for m in moments if m is not None)
        age = current - last_active
        if age <= timedelta(days=ACTIVE_DAYS):
            status = ActualityStatus.ACTIVE
        elif age <= timedelta(days=RECENT_DAYS):
            status = ActualityStatus.RECENT
        else:
            status = ActualityStatus.STALE
        return Actuality(
            status=status,
            last_active_at=last_active,
            tasks_assigned=counts.get("task_assigned", 0),
            tasks_submitted=counts.get("task_submitted", 0),
            tasks_passed=counts.get("task_reviewed:passed", 0),
            tasks_failed=counts.get("task_reviewed:failed", 0),
            tasks_expired=counts.get("task_expired", 0),
            employer_tests_completed=counts.get("employer_test_completed", 0),
        )

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
                "verified_grade": profile.verified_grade,
                "verified_specialization": profile.verified_specialization,
                "grade_verified_at": profile.grade_verified_at,
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
                "actuality": await self.actuality(profile),
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

    async def public_view(
        self, user_id: uuid.UUID, employer_id: uuid.UUID | None
    ) -> PublicProfileResponse:
        """Профиль для работодателя с учётом настроек приватности.

        Опубликованный профиль видят все работодатели. Работодатель, чьё
        приглашение кандидат принял, видит профиль и контакты всегда
        (пока профиль не удалён).
        """
        profile = await self.profiles.get(user_id)
        granted = (
            profile is not None
            and employer_id is not None
            and await self.profiles.has_contact_grant(user_id, employer_id)
        )
        if profile is None or (
            profile.status != ProfileStatus.PUBLISHED and not granted
        ):
            raise _profile_not_found()
        # Отозвано согласие на обработку персональных данных — профиль
        # не показывается никому, даже работодателю с открытым доступом.
        if not await self.consents.has(user_id, ConsentType.PERSONAL_DATA):
            raise _profile_not_found()
        privacy = privacy_of(profile)
        contact_access = ContactAccess.GRANTED if granted else ContactAccess.HIDDEN
        show_contacts = granted
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
                "contact_access": contact_access,
                "phone": profile.phone if show_contacts else None,
                "contact_email": profile.contact_email if show_contacts else None,
                "telegram": profile.telegram if show_contacts else None,
                "salary_from": profile.salary_from if privacy.show_salary else None,
                "salary_currency": (
                    profile.salary_currency if privacy.show_salary else None
                ),
                "has_photo": privacy.show_photo
                and await self.profiles.has_photo(user_id),
                "actuality": await self.actuality(profile),
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
            "industry": profile.industry,
            "category": category_of(profile),
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
