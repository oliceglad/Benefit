"""Внутренний API: с кем из кандидатов у работодателя уже был контакт
(для подборки в employer-service / matching-service)."""

import uuid

from benefit_common.internal import verify_internal_token
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import SessionDep
from app.models import Application, Invitation

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)

# Отказ кандидата важнее более позднего события: такого кандидата скрываем.
STICKY = {"invitation:declined", "application:rejected"}


@router.get("/employers/{employer_id}/contacts")
async def employer_contacts(
    employer_id: uuid.UUID, session: SessionDep
) -> dict[str, str]:
    """``{candidate_id: "invitation:<статус>" | "application:<статус>"}`` —
    последний статус взаимодействия."""
    events: list[tuple[object, uuid.UUID, str]] = []
    for model, kind in ((Invitation, "invitation"), (Application, "application")):
        rows = await session.execute(
            select(model.created_at, model.candidate_id, model.status).where(
                model.employer_id == employer_id
            )
        )
        events += [
            (created, candidate, f"{kind}:{status}")
            for created, candidate, status in rows
        ]
    contacts: dict[str, str] = {}
    for _, candidate_id, status in sorted(events, key=lambda e: e[0]):
        key = str(candidate_id)
        if contacts.get(key) not in STICKY:
            contacts[key] = status
    return contacts
