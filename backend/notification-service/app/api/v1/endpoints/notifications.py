"""Уведомления текущего пользователя (кандидата или работодателя)."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from benefit_common.errors import NotFoundError
from benefit_common.security import CurrentPrincipal
from fastapi import APIRouter, Query, status
from sqlalchemy import func, select, update

from app.api.deps import SessionDep
from app.models import Notification
from app.schemas.notification import NotificationList, NotificationResponse

router = APIRouter(tags=["notifications"])


async def _unread_count(session: SessionDep, user_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).where(
                Notification.user_id == user_id, Notification.read_at.is_(None)
            )
        )
        or 0
    )


@router.get("", response_model=NotificationList)
async def list_notifications(
    principal: CurrentPrincipal,
    session: SessionDep,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationList:
    query = select(Notification).where(Notification.user_id == principal.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    items = await session.scalars(
        query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    )
    return NotificationList(
        items=[NotificationResponse.model_validate(n) for n in items],
        unread_count=await _unread_count(session, principal.id),
    )


@router.get("/unread-count")
async def unread_count(principal: CurrentPrincipal, session: SessionDep) -> dict:
    return {"unread_count": await _unread_count(session, principal.id)}


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notification_id: uuid.UUID, principal: CurrentPrincipal, session: SessionDep
) -> None:
    notification = await session.get(Notification, notification_id)
    # Чужие уведомления неотличимы от несуществующих.
    if notification is None or notification.user_id != principal.id:
        raise NotFoundError("Уведомление не найдено")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        await session.commit()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(principal: CurrentPrincipal, session: SessionDep) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == principal.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await session.commit()
