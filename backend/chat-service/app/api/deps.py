"""Общие зависимости FastAPI."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.chat import ChatService
from app.services.storage import FileStorage, get_storage
from app.services.tasks import TaskService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
StorageDep = Annotated[FileStorage, Depends(get_storage)]


def get_chat_service(session: SessionDep, storage: StorageDep) -> ChatService:
    return ChatService(session, storage)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


def get_task_service(session: SessionDep, chat: ChatServiceDep) -> TaskService:
    return TaskService(session, chat)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
