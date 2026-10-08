"""Приглашения: работодатель отправляет, кандидат принимает или отклоняет."""

import uuid

from benefit_common.security import Candidate, CurrentPrincipal, Employer
from fastapi import APIRouter, status

from app.api.deps import InvitationServiceDep
from app.models import InvitationStatus
from app.schemas.invitation import InvitationCreate, InvitationReply, InvitationResponse
from app.services.invitations import to_response

router = APIRouter(tags=["invitations"])


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    data: InvitationCreate, employer: Employer, service: InvitationServiceDep
) -> InvitationResponse:
    """Пригласить опубликованного кандидата на вакансию.

    Кандидат получит уведомление в личном кабинете и на почту.
    """
    return to_response(await service.create(employer, data))


@router.get("/incoming", response_model=list[InvitationResponse])
async def incoming(
    candidate: Candidate,
    service: InvitationServiceDep,
    status: InvitationStatus | None = None,
) -> list[InvitationResponse]:
    """Входящие приглашения кандидата: вакансия, зарплата, статус."""
    return [to_response(i) for i in await service.incoming(candidate, status)]


@router.get("/sent", response_model=list[InvitationResponse])
async def sent(
    employer: Employer,
    service: InvitationServiceDep,
    status: InvitationStatus | None = None,
) -> list[InvitationResponse]:
    return [to_response(i) for i in await service.sent(employer, status)]


@router.get("/{invitation_id}", response_model=InvitationResponse)
async def get_invitation(
    invitation_id: uuid.UUID, principal: CurrentPrincipal, service: InvitationServiceDep
) -> InvitationResponse:
    return to_response(await service.get(principal, invitation_id))


@router.post("/{invitation_id}/accept", response_model=InvitationResponse)
async def accept(
    invitation_id: uuid.UUID,
    candidate: Candidate,
    service: InvitationServiceDep,
    reply: InvitationReply | None = None,
) -> InvitationResponse:
    invitation = await service.respond(
        candidate, invitation_id, reply or InvitationReply(), accept=True
    )
    return to_response(invitation)


@router.post("/{invitation_id}/decline", response_model=InvitationResponse)
async def decline(
    invitation_id: uuid.UUID,
    candidate: Candidate,
    service: InvitationServiceDep,
    reply: InvitationReply | None = None,
) -> InvitationResponse:
    invitation = await service.respond(
        candidate, invitation_id, reply or InvitationReply(), accept=False
    )
    return to_response(invitation)


@router.post("/{invitation_id}/withdraw", response_model=InvitationResponse)
async def withdraw(
    invitation_id: uuid.UUID, employer: Employer, service: InvitationServiceDep
) -> InvitationResponse:
    return to_response(await service.withdraw(employer, invitation_id))
