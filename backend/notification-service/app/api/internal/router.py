"""Внутренний API: другие сервисы создают уведомления пользователям."""

from benefit_common.internal import verify_internal_token
from benefit_common.outbox import enqueue
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select

from app.api.deps import SessionDep
from app.models import EmailDelivery, Notification
from app.schemas.notification import NotificationCreate, NotificationResponse
from app.services.delivery import EMAIL_KIND, build_email_payload

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)


@router.post(
    "/notifications",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification(
    data: NotificationCreate, session: SessionDep, response: Response
) -> NotificationResponse:
    """Создаёт уведомление и ставит письмо в очередь отправки.

    Идемпотентно по ``dedup_key``: повторный вызов возвращает уже
    созданное уведомление (200), не дублируя его и письмо.
    """
    if data.dedup_key:
        existing = await session.scalar(
            select(Notification).where(Notification.dedup_key == data.dedup_key)
        )
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return NotificationResponse.model_validate(existing)

    notification = Notification(
        user_id=data.user_id,
        type=data.type,
        title=data.title,
        body=data.body,
        link=data.link,
        data=data.data,
        dedup_key=data.dedup_key,
    )
    session.add(notification)
    await session.flush()
    if data.email:
        enqueue(
            session,
            EmailDelivery,
            EMAIL_KIND,
            build_email_payload(
                notification.id, data.user_id, data.title, data.body, data.link
            ),
        )
    await session.commit()
    await session.refresh(notification)
    return NotificationResponse.model_validate(notification)
