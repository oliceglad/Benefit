"""Преобразование уведомлений LISTEN/NOTIFY в события для клиентов."""

import uuid
from typing import Any

from app.db.session import async_session_factory
from app.models import Conversation, Task
from app.schemas.chat import TaskResponse
from app.services.chat import ChatService, message_response
from app.services.storage import get_storage


async def resolve_event(payload: dict[str, Any]) -> dict[str, Any] | None:
    event_type = payload["type"]
    if event_type not in ("message.created", "task.updated", "conversation.updated"):
        # typing, conversation.read — данные уже в уведомлении.
        return payload
    async with async_session_factory() as session:
        if event_type == "message.created":
            message = await ChatService(session, get_storage()).load_message(
                uuid.UUID(payload["message_id"])
            )
            if message is None:
                return None
            return {
                "type": event_type,
                "message": message_response(message).model_dump(mode="json"),
            }
        if event_type == "task.updated":
            task = await session.get(Task, uuid.UUID(payload["task_id"]))
            if task is None:
                return None
            return {
                "type": event_type,
                "task": TaskResponse.model_validate(task).model_dump(mode="json"),
            }
        conversation = await session.get(
            Conversation, uuid.UUID(payload["conversation_id"])
        )
        if conversation is None:
            return None
        return {
            "type": event_type,
            "conversation": {
                "id": str(conversation.id),
                "status": conversation.status,
                "invitation_status": conversation.invitation_status,
            },
        }
