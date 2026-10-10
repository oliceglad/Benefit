"""Внутренний API: applications-service синхронизирует диалоги с приглашениями,
auth-service сообщает об удалении аккаунта."""

import uuid

from benefit_common.errors import NotFoundError
from benefit_common.internal import verify_internal_token
from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, or_, select

from app.api.deps import ChatServiceDep, SessionDep, StorageDep, TaskServiceDep
from app.models import Attachment, Conversation, ConversationStatus, MessageKind
from app.schemas.chat import ConversationInfo, ConversationSync, InternalMessage

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)


@router.put("/conversations")
async def sync_conversation(
    data: ConversationSync,
    chat: ChatServiceDep,
    tasks: TaskServiceDep,
    session: SessionDep,
) -> dict[str, str]:
    """Создаёт диалог по приглашению или обновляет его статус. Идемпотентно."""
    conversation = await chat.sync_invitation(data)
    if conversation.status == ConversationStatus.CLOSED:
        await tasks.close_for_conversation(conversation)
        await session.commit()
    return {"conversation_id": str(conversation.id), "status": conversation.status}


async def _conversation(
    session: SessionDep, conversation_id: uuid.UUID
) -> Conversation:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        raise NotFoundError("Диалог не найден", code="conversation_not_found")
    return conversation


@router.get("/conversations/{conversation_id}", response_model=ConversationInfo)
async def get_conversation(
    conversation_id: uuid.UUID, session: SessionDep
) -> ConversationInfo:
    """Участники и статус диалога (для проверки прав в других сервисах)."""
    return ConversationInfo.model_validate(
        await _conversation(session, conversation_id)
    )


@router.post("/conversations/{conversation_id}/messages", status_code=201)
async def post_message(
    conversation_id: uuid.UUID,
    data: InternalMessage,
    chat: ChatServiceDep,
    session: SessionDep,
) -> dict[str, str]:
    """Сообщение от другого сервиса. Идемпотентно по ``client_id``."""
    conversation = await _conversation(session, conversation_id)
    if data.sender_id is not None and not conversation.is_participant(data.sender_id):
        raise NotFoundError("Отправитель не участник диалога", code="not_participant")
    await chat.add_service_message(
        conversation,
        MessageKind(data.kind),
        data.text,
        data.client_id,
        sender_id=data.sender_id,
        data=data.data,
    )
    await session.commit()
    return {"status": "ok"}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID, session: SessionDep, storage: StorageDep
) -> None:
    """Аккаунт удалён: переписки пользователя с сообщениями, заданиями и
    файлами вложений. Идемпотентно."""
    involved = or_(
        Conversation.candidate_id == user_id, Conversation.employer_id == user_id
    )
    keys = list(
        await session.scalars(
            select(Attachment.storage_key)
            .join(Conversation, Attachment.conversation_id == Conversation.id)
            .where(involved)
        )
    )
    # Сначала файлы, потом записи: если удаление прервётся, повторная
    # доставка снова найдёт записи (удаление уже стёртого файла не падает).
    for key in keys:
        await storage.delete(key)
    await session.execute(delete(Conversation).where(involved))
    await session.commit()
