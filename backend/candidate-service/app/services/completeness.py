"""Заполненность профиля и шаги онбординга после регистрации."""

from dataclasses import dataclass

from app.models.candidate import CandidateProfile
from app.schemas.profile import Completeness, OnboardingStep


@dataclass(frozen=True)
class _Check:
    field: str
    step: str
    required: bool


# Порядок шагов — порядок экранов онбординга на фронтенде.
STEPS = [
    ("personal", "Личные данные"),
    ("contacts", "Контакты"),
    ("specialization", "Специализация и грейд"),
    ("skills", "Навыки"),
    ("experience", "Опыт и образование"),
    ("preferences", "Пожелания к работе"),
    ("consents", "Согласия и приватность"),
]

CHECKS = [
    _Check("last_name", "personal", required=True),
    _Check("first_name", "personal", required=True),
    _Check("birth_date", "personal", required=False),
    _Check("city", "personal", required=False),
    _Check("photo", "personal", required=False),
    _Check("contacts", "contacts", required=True),
    _Check("links", "contacts", required=False),
    _Check("headline", "specialization", required=True),
    _Check("grade", "specialization", required=True),
    _Check("roles", "specialization", required=True),
    _Check("about", "specialization", required=False),
    _Check("industry", "specialization", required=False),
    _Check("skills", "skills", required=True),
    _Check("soft_skills", "skills", required=False),
    _Check("languages", "skills", required=False),
    # Опыт работы, пет-проекты или образование: у стажёров может не быть
    # коммерческого опыта, но что-то о себе показать нужно.
    _Check("experience_or_projects", "experience", required=True),
    _Check("education", "experience", required=False),
    _Check("salary_from", "preferences", required=False),
    _Check("work_formats", "preferences", required=False),
    _Check("consents", "consents", required=True),
]


def _filled(
    profile: CandidateProfile, field: str, *, has_photo: bool, has_consents: bool
) -> bool:
    match field:
        case "photo":
            return has_photo
        case "contacts":
            return bool(profile.phone or profile.contact_email or profile.telegram)
        case "experience_or_projects":
            return bool(profile.experience or profile.projects or profile.education)
        case "consents":
            return has_consents
        case _:
            return bool(getattr(profile, field))


def evaluate(
    profile: CandidateProfile, *, has_photo: bool, has_consents: bool
) -> Completeness:
    filled = {
        check.field: _filled(
            profile, check.field, has_photo=has_photo, has_consents=has_consents
        )
        for check in CHECKS
    }
    missing_required = [c.field for c in CHECKS if c.required and not filled[c.field]]
    missing_recommended = [
        c.field for c in CHECKS if not c.required and not filled[c.field]
    ]
    # Обязательные поля весят вдвое больше рекомендуемых.
    total = sum(2 if c.required else 1 for c in CHECKS)
    score = sum(2 if c.required else 1 for c in CHECKS if filled[c.field])

    steps = [
        OnboardingStep(
            id=step_id,
            title=title,
            completed=all(
                filled[c.field] for c in CHECKS if c.step == step_id and c.required
            ),
        )
        for step_id, title in STEPS
    ]
    next_step = next((s.id for s in steps if not s.completed), None)
    return Completeness(
        percent=round(score * 100 / total),
        can_publish=not missing_required,
        missing_required=missing_required,
        missing_recommended=missing_recommended,
        onboarding_completed=next_step is None,
        next_step=next_step,
        steps=steps,
    )
