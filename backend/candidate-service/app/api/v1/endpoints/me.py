"""Личный кабинет кандидата: профиль, резюме, фото, согласия, ФСП.

Доступ только у роли «кандидат» и только к собственному профилю.
"""

import logging
from typing import Annotated

from benefit_common.errors import AppError
from fastapi import APIRouter, Query, Request, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import (
    Candidate,
    FspSyncServiceDep,
    MyProfile,
    ProfileServiceDep,
    ResumeParserDep,
    SessionDep,
)
from app.api.responses import pdf_response
from app.core.config import settings
from app.models.candidate import CandidatePhoto
from app.schemas.consent import ConsentGrant, ConsentStatus, ConsentType
from app.schemas.profile import ProfileResponse, ProfileUpdate, ResumeImportResponse
from app.services.consents import ConsentService
from app.services.pdf_export import build_context, render_resume_pdf
from app.services.pdf_import import extract_text
from app.services.photos import process_photo
from app.services.resume_import import merge_into, validate_draft

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["candidate: личный кабинет"])


@router.get("", response_model=ProfileResponse)
async def get_profile(
    profile: MyProfile, service: ProfileServiceDep
) -> ProfileResponse:
    """Профиль текущего кандидата. При первом обращении создаётся черновик.

    ``completeness`` подсказывает фронтенду шаги онбординга после регистрации.
    """
    return await service.to_response(profile)


@router.patch("", response_model=ProfileResponse)
async def update_profile(
    data: ProfileUpdate, profile: MyProfile, service: ProfileServiceDep
) -> ProfileResponse:
    """Частичное обновление: передаются только изменённые поля или разделы.

    Списки (опыт, навыки…) заменяются целиком.
    """
    profile = await service.update(profile, data)
    return await service.to_response(profile)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile: MyProfile, service: ProfileServiceDep) -> None:
    """Удаление профиля и всех данных резюме."""
    await service.delete(profile)


@router.post("/publish", response_model=ProfileResponse)
async def publish(profile: MyProfile, service: ProfileServiceDep) -> ProfileResponse:
    """Публикация: профиль становится доступен работодателям.

    Требует заполненных обязательных полей и действующих согласий.
    """
    profile = await service.publish(profile)
    return await service.to_response(profile)


@router.post("/unpublish", response_model=ProfileResponse)
async def unpublish(profile: MyProfile, service: ProfileServiceDep) -> ProfileResponse:
    profile = await service.unpublish(profile)
    return await service.to_response(profile)


# --- Фото -------------------------------------------------------------------


@router.put("/photo", status_code=status.HTTP_204_NO_CONTENT)
async def upload_photo(
    file: UploadFile, profile: MyProfile, session: SessionDep
) -> None:
    raw = await file.read(settings.photo_max_bytes + 1)
    content = await run_in_threadpool(process_photo, raw)
    photo = await session.get(CandidatePhoto, profile.user_id)
    if photo is None:
        session.add(
            CandidatePhoto(
                user_id=profile.user_id, content=content, content_type="image/jpeg"
            )
        )
    else:
        photo.content = content
    await session.commit()


@router.get("/photo", response_class=Response)
async def get_photo(profile: MyProfile, session: SessionDep) -> Response:
    photo = await session.get(CandidatePhoto, profile.user_id)
    if photo is None:
        raise AppError("Фото не загружено", code="photo_not_found", status_code=404)
    return Response(
        photo.content,
        media_type=photo.content_type,
        headers={"Cache-Control": "private, max-age=60"},
    )


@router.delete("/photo", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(profile: MyProfile, session: SessionDep) -> None:
    photo = await session.get(CandidatePhoto, profile.user_id)
    if photo is not None:
        await session.delete(photo)
        await session.commit()


# --- Согласия -------------------------------------------------------------------


@router.get("/consents", response_model=list[ConsentStatus])
async def list_consents(
    principal: Candidate, session: SessionDep
) -> list[ConsentStatus]:
    return await ConsentService(session).statuses(principal.id)


@router.post("/consents", response_model=list[ConsentStatus])
async def grant_consent(
    data: ConsentGrant, request: Request, principal: Candidate, session: SessionDep
) -> list[ConsentStatus]:
    """Фиксирует согласие с версией документа, временем, IP и браузером."""
    service = ConsentService(session)
    ip = request.headers.get("x-real-ip") or (
        request.client.host if request.client else None
    )
    await service.grant(
        principal.id,
        data,
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return await service.statuses(principal.id)


@router.delete("/consents/{consent_type}", response_model=list[ConsentStatus])
async def revoke_consent(
    consent_type: ConsentType,
    principal: Candidate,
    session: SessionDep,
    profiles: ProfileServiceDep,
) -> list[ConsentStatus]:
    """Отзыв согласия. Опубликованный профиль снимается с публикации."""
    service = ConsentService(session)
    await service.revoke(principal.id, consent_type)
    await session.commit()
    await profiles.revoke_consent_effects(await profiles.profiles.get(principal.id))
    return await service.statuses(principal.id)


# --- ФСП ------------------------------------------------------------------------


@router.post("/fsp/sync", response_model=ProfileResponse)
async def sync_fsp(
    profile: MyProfile, sync: FspSyncServiceDep, service: ProfileServiceDep
) -> ProfileResponse:
    """Обновляет связь с участником ФСП и его достижения.

    Вызывать после привязки ФСП ID (``POST /api/v1/auth/oauth/fsp_id/link``).
    """
    await sync.sync(profile)
    return await service.to_response(profile)


# --- Резюме: импорт и экспорт PDF --------------------------------------------------


@router.post("/resume/import", response_model=ResumeImportResponse)
async def import_resume(
    file: UploadFile,
    profile: MyProfile,
    service: ProfileServiceDep,
    parser: ResumeParserDep,
    apply: Annotated[
        bool,
        Query(description="Сразу дополнить профиль (заполненные поля не меняются)"),
    ] = False,
) -> ResumeImportResponse:
    """Распознаёт резюме из PDF (например, выгрузку с hh.ru).

    Без ``apply`` только возвращает черновик для предзаполнения формы.
    """
    raw = await file.read(settings.resume_import_max_bytes + 1)
    text = await run_in_threadpool(extract_text, raw)
    parsed = await run_in_threadpool(parser.parse, text)
    draft = validate_draft(parsed)

    applied_fields: list[str] = []
    if apply and draft:
        changes, applied_fields = merge_into(profile, draft)
        if applied_fields:
            await service.update(profile, changes)
    return ResumeImportResponse(
        draft=draft,
        warnings=parsed.warnings,
        applied=bool(applied_fields),
        applied_fields=applied_fields,
    )


@router.get("/resume.pdf", response_class=Response)
async def export_resume(
    profile: MyProfile, service: ProfileServiceDep, session: SessionDep
) -> Response:
    """Резюме в PDF со всеми данными (для себя или отправки работодателю)."""
    data = await service.to_response(profile)
    photo = await session.get(CandidatePhoto, profile.user_id)
    context = build_context(data, photo.content if photo else None)
    pdf = await run_in_threadpool(render_resume_pdf, context)
    return pdf_response(pdf, data.last_name)
