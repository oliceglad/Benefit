"""Применение черновика из PDF к профилю."""

from typing import Any

from pydantic import ValidationError

from app.models.candidate import CandidateProfile
from app.schemas.profile import ProfileUpdate
from app.services.pdf_import import ParsedResume

# Списки, которые дополняются новыми элементами (по ключу).
MERGEABLE_LISTS = {
    "skills": lambda item: item["name"].lower(),
    "soft_skills": lambda item: item.lower(),
    "roles": lambda item: item,
    "languages": lambda item: item["language"].lower(),
    "links": lambda item: item["url"],
}
# Списки, которые заполняются, только если в профиле они пусты.
REPLACEABLE_LISTS = {"experience", "education", "courses", "projects"}


def validate_draft(parsed: ParsedResume) -> dict[str, Any]:
    """Оставляет только поля, прошедшие валидацию профиля."""
    valid: dict[str, Any] = {}
    for key, value in parsed.draft.items():
        try:
            model = ProfileUpdate.model_validate({key: value})
        except ValidationError:
            parsed.warnings.append(f"Поле «{key}» распознано некорректно и пропущено")
            continue
        valid[key] = model.model_dump(mode="json", include={key})[key]
    return valid


def merge_into(
    profile: CandidateProfile, draft: dict[str, Any]
) -> tuple[ProfileUpdate, list[str]]:
    """Не перезаписывает данные, уже заполненные пользователем."""
    changes: dict[str, Any] = {}
    for key, value in draft.items():
        current = getattr(profile, key)
        if key in MERGEABLE_LISTS:
            key_of = MERGEABLE_LISTS[key]
            existing = {key_of(item) for item in current}
            added = [item for item in value if key_of(item) not in existing]
            if added:
                changes[key] = [*current, *added]
        elif key in REPLACEABLE_LISTS:
            if not current:
                changes[key] = value
        elif current in (None, ""):
            changes[key] = value
    return ProfileUpdate.model_validate(changes), sorted(changes)
