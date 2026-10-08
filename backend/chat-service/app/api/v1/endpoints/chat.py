"""Переписка: диалоги, сообщения, файлы (REST).

Новые события приходят по WebSocket (``/ws``); отправлять сообщения
можно и через REST, и через WebSocket.
"""

import uuid
from typing import Annotated
from urllib.parse import quote

from benefit_common.security import CurrentPrincipal
from fastapi import APIRouter, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.deps import ChatServiceDep
from app.core.config import settings
from app.schemas.chat import (
    AttachmentResponse,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    ReadRequest,
)
from app.services.chat import message_response

router = APIRouter(tags=["chat"])


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    principal: CurrentPrincipal,
    service: ChatServiceDep,
    invitation_id: uuid.UUID | None = None,
) -> list[ConversationResponse]:
    """Диалоги текущего пользователя (с числом непрочитанных)."""
    return await service.list_conversations(principal, invitation_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID, principal: CurrentPrincipal, service: ChatServiceDep
) -> ConversationResponse:
    conversation = await service.get_conversation(principal, conversation_id)
    return await service.view(conversation, principal.id)


@router.get(
    "/conversations/{conversation_id}/messages", response_model=list[MessageResponse]
)
async def list_messages(
    conversation_id: uuid.UUID,
    principal: CurrentPrincipal,
    service: ChatServiceDep,
    before: Annotated[
        uuid.UUID | None, Query(description="Загрузить сообщения до этого")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MessageResponse]:
    return await service.messages(principal, conversation_id, before, limit)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: uuid.UUID,
    data: MessageCreate,
    principal: CurrentPrincipal,
    service: ChatServiceDep,
) -> MessageResponse:
    return message_response(await service.send(principal, conversation_id, data))


@router.post(
    "/conversations/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT
)
async def mark_read(
    conversation_id: uuid.UUID,
    data: ReadRequest,
    principal: CurrentPrincipal,
    service: ChatServiceDep,
) -> None:
    await service.mark_read(principal, conversation_id, data.message_id)


@router.post(
    "/conversations/{conversation_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    conversation_id: uuid.UUID,
    file: UploadFile,
    principal: CurrentPrincipal,
    service: ChatServiceDep,
) -> AttachmentResponse:
    """Загрузить файл; затем передать его id в ``attachment_ids`` сообщения."""
    data = await file.read(settings.max_file_bytes + 1)
    attachment = await service.upload(
        principal, conversation_id, file.filename or "file", data
    )
    return AttachmentResponse.model_validate(attachment)


@router.get("/attachments/{attachment_id}", response_class=StreamingResponse)
async def download_attachment(
    attachment_id: uuid.UUID, principal: CurrentPrincipal, service: ChatServiceDep
) -> StreamingResponse:
    attachment, stream = await service.download(principal, attachment_id)
    return StreamingResponse(
        stream,
        media_type=attachment.content_type,
        headers={
            # Всегда скачивание: загруженный файл не исполняется в браузере.
            "Content-Disposition": "attachment; filename=file; "
            f"filename*=UTF-8''{quote(attachment.filename)}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "private, max-age=3600",
            "Content-Length": str(attachment.size),
        },
    )
