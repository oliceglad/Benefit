"""Переписка кандидата и работодателя.

Диалог создаётся вместе с приглашением (applications-service) — писать
могут только два его участника. Отклонённое или отозванное приглашение
закрывает диалог: история остаётся, новые сообщения отправить нельзя.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from benefit_common.errors import AppError, ConflictError, NotFoundError
from benefit_common.security import Principal
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import (
    Attachment,
    Conversation,
    ConversationStatus,
    Message,
    MessageKind,
)
from app.schemas.chat import (
    AttachmentResponse,
    ConversationResponse,
    ConversationSync,
    MessageCreate,
    MessageResponse,
)
from app.services import realtime
from app.services.delivery import notify
from app.services.files import validate_upload
from app.services.storage import FileStorage

logger = logging.getLogger(__name__)

# Отказ или отзыв (приглашения или отклика) закрывает переписку.
CLOSING_STATUSES = {"declined", "withdrawn", "rejected"}


def now() -> datetime:
    return datetime.now(UTC)


def message_response(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        kind=message.kind,
        text=message.text,
        task_id=message.task_id,
        client_id=message.client_id,
        data=message.data or {},
        attachments=[AttachmentResponse.model_validate(a) for a in message.attachments],
        created_at=message.created_at,
    )


def preview(message: Message) -> str:
    if message.text:
        return message.text[:300]
    names = ", ".join(a.filename for a in message.attachments)
    return f"Файлы: {names}" if names else ""


class ChatService:
    def __init__(self, session: AsyncSession, storage: FileStorage) -> None:
        self.session = session
        self.storage = storage

    # --- Диалоги -------------------------------------------------------------

    async def get_conversation(
        self, principal: Principal, conversation_id: uuid.UUID
    ) -> Conversation:
        conversation = await self.session.get(Conversation, conversation_id)
        # Чужие диалоги неотличимы от несуществующих.
        if conversation is None or not conversation.is_participant(principal.id):
            raise NotFoundError("Диалог не найден", code="conversation_not_found")
        return conversation

    async def list_conversations(
        self, principal: Principal, invitation_id: uuid.UUID | None = None
    ) -> list[ConversationResponse]:
        query = select(Conversation).where(
            or_(
                Conversation.candidate_id == principal.id,
                Conversation.employer_id == principal.id,
            )
        )
        if invitation_id is not None:
            query = query.where(Conversation.invitation_id == invitation_id)
        conversations = await self.session.scalars(
            query.order_by(
                Conversation.last_message_at.desc().nulls_last(),
                Conversation.created_at.desc(),
            )
        )
        return [await self.view(c, principal.id) for c in conversations]

    async def view(
        self, conversation: Conversation, user_id: uuid.UUID
    ) -> ConversationResponse:
        is_candidate = user_id == conversation.candidate_id
        my_read = (
            conversation.candidate_last_read_at
            if is_candidate
            else conversation.employer_last_read_at
        )
        other_read = (
            conversation.employer_last_read_at
            if is_candidate
            else conversation.candidate_last_read_at
        )
        unread_query = select(func.count()).where(
            Message.conversation_id == conversation.id,
            or_(Message.sender_id.is_(None), Message.sender_id != user_id),
        )
        if my_read is not None:
            unread_query = unread_query.where(Message.created_at > my_read)
        last = await self.session.scalar(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .options(selectinload(Message.attachments))
            .order_by(Message.seq.desc())
            .limit(1)
        )
        return ConversationResponse(
            id=conversation.id,
            source=conversation.source,
            invitation_id=conversation.invitation_id,
            candidate_id=conversation.candidate_id,
            employer_id=conversation.employer_id,
            vacancy_title=conversation.vacancy_title,
            company_name=conversation.company_name,
            invitation_status=conversation.invitation_status,
            status=conversation.status,
            last_message=message_response(last) if last else None,
            last_message_at=conversation.last_message_at,
            unread_count=await self.session.scalar(unread_query) or 0,
            other_party_last_read_at=other_read,
            created_at=conversation.created_at,
        )

    # --- Сообщения ---------------------------------------------------------------

    async def messages(
        self,
        principal: Principal,
        conversation_id: uuid.UUID,
        before: uuid.UUID | None,
        limit: int,
    ) -> list[MessageResponse]:
        """Страница истории (по возрастанию времени), до сообщения ``before``."""
        await self.get_conversation(principal, conversation_id)
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .options(selectinload(Message.attachments))
        )
        if before is not None:
            anchor = await self.session.get(Message, before)
            if anchor is None or anchor.conversation_id != conversation_id:
                raise NotFoundError("Сообщение не найдено", code="message_not_found")
            query = query.where(Message.seq < anchor.seq)
        page = list(
            await self.session.scalars(query.order_by(Message.seq.desc()).limit(limit))
        )
        return [message_response(m) for m in reversed(page)]

    async def load_message(self, message_id: uuid.UUID) -> Message | None:
        return await self.session.scalar(
            select(Message)
            .where(Message.id == message_id)
            .options(selectinload(Message.attachments))
        )

    async def send(
        self,
        principal: Principal,
        conversation_id: uuid.UUID,
        data: MessageCreate,
        *,
        kind: MessageKind = MessageKind.TEXT,
        task_id: uuid.UUID | None = None,
        notify_other: bool = True,
        commit: bool = True,
    ) -> Message:
        conversation = await self.get_conversation(principal, conversation_id)
        if conversation.status != ConversationStatus.OPEN:
            raise ConflictError(
                "Переписка закрыта: приглашение отклонено или отозвано",
                code="conversation_closed",
            )
        text = data.text.strip()
        if not text and not data.attachment_ids:
            raise AppError("Пустое сообщение", code="empty_message", status_code=422)

        if data.client_id:
            existing = await self._by_client_id(conversation.id, data.client_id)
            if existing is not None:
                if existing.sender_id != principal.id:
                    raise ConflictError(
                        "client_id уже занят", code="client_id_conflict"
                    )
                return existing

        attachments = await self._claim_attachments(
            conversation.id, principal.id, data.attachment_ids
        )
        created_at = now()
        message = Message(
            conversation_id=conversation.id,
            sender_id=principal.id,
            kind=kind,
            text=text,
            task_id=task_id,
            client_id=data.client_id,
            created_at=created_at,
        )
        self.session.add(message)
        try:
            await self.session.flush()
        except IntegrityError:
            # Параллельная отправка с тем же client_id.
            await self.session.rollback()
            existing = await self._by_client_id(conversation_id, data.client_id or "")
            if existing is None:
                raise
            return existing
        for attachment in attachments:
            attachment.message_id = message.id

        conversation.last_message_at = created_at
        # Своё сообщение — значит, переписка прочитана.
        self._set_read(conversation, principal.id, created_at)
        await realtime.publish(
            self.session,
            [conversation.candidate_id, conversation.employer_id],
            "message.created",
            message_id=message.id,
        )
        if notify_other:
            self._notify_new_message(conversation, principal.id, text, attachments)
        if commit:
            await self.session.commit()
        return await self.load_message(message.id)  # type: ignore[return-value]

    async def add_system_message(
        self, conversation: Conversation, text: str, client_id: str
    ) -> Message | None:
        """Системное сообщение (идемпотентно по ``client_id``)."""
        return await self.add_service_message(
            conversation, MessageKind.SYSTEM, text, client_id
        )

    async def add_service_message(
        self,
        conversation: Conversation,
        kind: MessageKind,
        text: str,
        client_id: str,
        *,
        sender_id: uuid.UUID | None = None,
        data: dict | None = None,
    ) -> Message | None:
        """Сообщение от системы или другого сервиса (идемпотентно)."""
        if await self._by_client_id(conversation.id, client_id) is not None:
            return None
        created_at = now()
        message = Message(
            conversation_id=conversation.id,
            sender_id=sender_id,
            kind=kind,
            text=text,
            client_id=client_id,
            data=data or {},
            created_at=created_at,
        )
        self.session.add(message)
        await self.session.flush()
        conversation.last_message_at = created_at
        await realtime.publish(
            self.session,
            [conversation.candidate_id, conversation.employer_id],
            "message.created",
            message_id=message.id,
        )
        return message

    async def mark_read(
        self,
        principal: Principal,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID | None = None,
    ) -> Conversation:
        conversation = await self.get_conversation(principal, conversation_id)
        read_at = now()
        if message_id is not None:
            message = await self.session.get(Message, message_id)
            if message is None or message.conversation_id != conversation.id:
                raise NotFoundError("Сообщение не найдено", code="message_not_found")
            read_at = message.created_at
        if self._set_read(conversation, principal.id, read_at):
            await realtime.publish(
                self.session,
                [conversation.other_party(principal.id)],
                "conversation.read",
                conversation_id=conversation.id,
                user_id=principal.id,
                last_read_at=read_at,
            )
            await self.session.commit()
        return conversation

    async def typing(self, principal: Principal, conversation_id: uuid.UUID) -> None:
        conversation = await self.get_conversation(principal, conversation_id)
        await realtime.publish(
            self.session,
            [conversation.other_party(principal.id)],
            "typing",
            conversation_id=conversation.id,
            user_id=principal.id,
        )
        await self.session.commit()

    # --- Файлы ---------------------------------------------------------------------

    async def upload(
        self,
        principal: Principal,
        conversation_id: uuid.UUID,
        filename: str,
        data: bytes,
    ) -> Attachment:
        conversation = await self.get_conversation(principal, conversation_id)
        if conversation.status != ConversationStatus.OPEN:
            raise ConflictError("Переписка закрыта", code="conversation_closed")
        name, content_type = validate_upload(filename, data)
        pending = await self.session.scalar(
            select(func.count()).where(
                Attachment.uploader_id == principal.id,
                Attachment.message_id.is_(None),
            )
        )
        if (pending or 0) >= settings.max_pending_attachments:
            raise AppError(
                "Слишком много неотправленных файлов: отправьте их в сообщении "
                "или повторите позже",
                code="too_many_pending_attachments",
                status_code=429,
            )
        key = await self.storage.save(data)
        attachment = Attachment(
            conversation_id=conversation.id,
            uploader_id=principal.id,
            filename=name,
            content_type=content_type,
            size=len(data),
            storage_key=key,
        )
        self.session.add(attachment)
        await self.session.commit()
        await self.session.refresh(attachment)
        return attachment

    async def download(
        self, principal: Principal, attachment_id: uuid.UUID
    ) -> tuple[Attachment, AsyncIterator[bytes]]:
        attachment = await self.session.get(Attachment, attachment_id)
        if attachment is None:
            raise NotFoundError("Файл не найден", code="attachment_not_found")
        await self.get_conversation(principal, attachment.conversation_id)
        # Неотправленный файл виден только загрузившему.
        if attachment.message_id is None and attachment.uploader_id != principal.id:
            raise NotFoundError("Файл не найден", code="attachment_not_found")
        return attachment, self.storage.open(attachment.storage_key)

    async def cleanup_orphans(self) -> int:
        """Удаляет загрузки, так и не прикреплённые к сообщению."""
        from datetime import timedelta

        threshold = now() - timedelta(hours=settings.orphan_attachment_ttl_hours)
        orphans = list(
            await self.session.scalars(
                select(Attachment).where(
                    Attachment.message_id.is_(None), Attachment.created_at < threshold
                )
            )
        )
        for attachment in orphans:
            await self.storage.delete(attachment.storage_key)
            await self.session.delete(attachment)
        await self.session.commit()
        return len(orphans)

    # --- Синхронизация с приглашениями -------------------------------------------

    async def sync_invitation(self, data: ConversationSync) -> Conversation:
        """Создаёт диалог по приглашению или обновляет его статус."""
        conversation = await self.session.scalar(
            select(Conversation)
            .where(Conversation.invitation_id == data.invitation_id)
            .with_for_update()
        )
        if conversation is None:
            conversation = Conversation(
                source=data.source,
                invitation_id=data.invitation_id,
                candidate_id=data.candidate_id,
                employer_id=data.employer_id,
                vacancy_title=data.vacancy_title,
                company_name=data.company_name,
                invitation_status=data.invitation_status,
                status=ConversationStatus.OPEN,
            )
            self.session.add(conversation)
            await self.session.flush()
        # Порядок доставки не гарантирован: закрытый диалог не открываем.
        if conversation.status == ConversationStatus.OPEN:
            conversation.invitation_status = data.invitation_status
            if data.invitation_status in CLOSING_STATUSES:
                conversation.status = ConversationStatus.CLOSED
        if data.event_text:
            await self.add_system_message(
                conversation, data.event_text, f"invitation:{data.event_key}"
            )
        await realtime.publish(
            self.session,
            [conversation.candidate_id, conversation.employer_id],
            "conversation.updated",
            conversation_id=conversation.id,
        )
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    # --- Внутреннее ------------------------------------------------------------------

    async def _by_client_id(
        self, conversation_id: uuid.UUID, client_id: str
    ) -> Message | None:
        return await self.session.scalar(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.client_id == client_id,
            )
            .options(selectinload(Message.attachments))
        )

    async def _claim_attachments(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, ids: list[uuid.UUID]
    ) -> list[Attachment]:
        if not ids:
            return []
        attachments = list(
            await self.session.scalars(
                select(Attachment)
                .where(
                    Attachment.id.in_(ids),
                    Attachment.conversation_id == conversation_id,
                    Attachment.uploader_id == user_id,
                    Attachment.message_id.is_(None),
                )
                .with_for_update()
            )
        )
        if len(attachments) != len(set(ids)):
            raise AppError(
                "Файл не найден или уже отправлен",
                code="invalid_attachments",
                status_code=422,
            )
        return attachments

    @staticmethod
    def _set_read(
        conversation: Conversation, user_id: uuid.UUID, read_at: datetime
    ) -> bool:
        field = (
            "candidate_last_read_at"
            if user_id == conversation.candidate_id
            else "employer_last_read_at"
        )
        current = getattr(conversation, field)
        if current is None or read_at > current:
            setattr(conversation, field, read_at)
            return True
        return False

    def _notify_new_message(
        self,
        conversation: Conversation,
        sender_id: uuid.UUID,
        text: str,
        attachments: list[Attachment],
    ) -> None:
        """Не чаще одного уведомления на диалог за окно времени."""
        recipient = conversation.other_party(sender_id)
        window = settings.message_notification_window_minutes * 60
        bucket = int(now().timestamp() // window)
        body = text[:300] or "Файлы: " + ", ".join(a.filename for a in attachments)
        notify(
            self.session,
            recipient,
            "chat.message",
            f"Сообщение: {conversation.company_name} — {conversation.vacancy_title}",
            body,
            f"/chat/{conversation.id}",
            f"chat:{conversation.id}:{recipient}:{bucket}",
            data={"conversation_id": str(conversation.id)},
        )
