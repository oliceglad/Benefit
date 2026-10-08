"""Просмотр опубликованных профилей работодателями.

Кандидаты сюда доступа не имеют: данные других кандидатов им недоступны.
Работодатель видит только опубликованные профили с учётом настроек
приватности кандидата.
"""

import uuid

from fastapi import APIRouter, Response
from fastapi.concurrency import run_in_threadpool

from app.api.deps import Employer, ProfileServiceDep, SessionDep
from app.api.responses import pdf_response
from app.core.exceptions import AppError
from app.models.candidate import CandidatePhoto
from app.schemas.profile import PublicProfileResponse
from app.services.pdf_export import build_context, render_resume_pdf

router = APIRouter(tags=["candidate: просмотр работодателем"])


@router.get("/{user_id}", response_model=PublicProfileResponse)
async def get_candidate(
    user_id: uuid.UUID, _: Employer, service: ProfileServiceDep
) -> PublicProfileResponse:
    return await service.public_view(user_id)


@router.get("/{user_id}/photo", response_class=Response)
async def get_candidate_photo(
    user_id: uuid.UUID, _: Employer, service: ProfileServiceDep, session: SessionDep
) -> Response:
    profile = await service.public_view(user_id)
    photo = await session.get(CandidatePhoto, user_id) if profile.has_photo else None
    if photo is None:
        raise AppError("Фото недоступно", code="photo_not_found", status_code=404)
    return Response(
        photo.content,
        media_type=photo.content_type,
        headers={"Cache-Control": "private, max-age=60"},
    )


@router.get("/{user_id}/resume.pdf", response_class=Response)
async def get_candidate_resume(
    user_id: uuid.UUID, _: Employer, service: ProfileServiceDep, session: SessionDep
) -> Response:
    profile = await service.public_view(user_id)
    photo = await session.get(CandidatePhoto, user_id) if profile.has_photo else None
    context = build_context(profile, photo.content if photo else None)
    pdf = await run_in_threadpool(render_resume_pdf, context)
    return pdf_response(pdf, profile.last_name)
