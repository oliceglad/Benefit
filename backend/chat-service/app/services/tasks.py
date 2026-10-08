"""Регулярные задания от работодателя.

Задание выдаётся в переписке: работодатель описывает задачу и срок,
кандидат решает её или предлагает подход (с файлами), работодатель
оценивает. Результаты уходят в candidate-service и влияют на
актуальность профиля. Повторяющееся задание (``recurrence_days``)
система выдаёт снова через заданный интервал.
"""

import logging
import uuid
from datetime import timedelta

from benefit_common.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from benefit_common.security import Principal
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    Conversation,
    ConversationStatus,
    MessageKind,
    ResponseType,
    Task,
    TaskStatus,
)
from app.schemas.chat import MessageCreate, TaskCreate, TaskReview, TaskSubmit
from app.services import realtime
from app.services.chat import ChatService, now
from app.services.delivery import notify, record_activity

logger = logging.getLogger(__name__)

MIN_DURATION = timedelta(minutes=10)
MAX_DURATION = timedelta(days=90)

RESULT_TITLES = {TaskStatus.PASSED: "принято", TaskStatus.FAILED: "не принято"}
RESPONSE_TITLES = {
    ResponseType.SOLUTION: "решение",
    ResponseType.APPROACH: "подход к решению",
}


def _task_link(task: Task) -> str:
    return f"/chat/{task.conversation_id}?task={task.id}"


class TaskService:
    def __init__(self, session: AsyncSession, chat: ChatService) -> None:
        self.session = session
        self.chat = chat

    async def get(self, principal: Principal, task_id: uuid.UUID) -> Task:
        task = await self.session.get(Task, task_id)
        if task is None or principal.id not in (task.candidate_id, task.employer_id):
            raise NotFoundError("Задание не найдено", code="task_not_found")
        return task

    async def list_tasks(
        self,
        principal: Principal,
        status: TaskStatus | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> list[Task]:
        query = select(Task).where(
            or_(Task.candidate_id == principal.id, Task.employer_id == principal.id)
        )
        if status is not None:
            query = query.where(Task.status == status)
        if conversation_id is not None:
            query = query.where(Task.conversation_id == conversation_id)
        return list(await self.session.scalars(query.order_by(Task.created_at.desc())))

    async def create(
        self, employer: Principal, conversation_id: uuid.UUID, data: TaskCreate
    ) -> Task:
        conversation = await self.chat.get_conversation(employer, conversation_id)
        if conversation.employer_id != employer.id:
            raise ForbiddenError("Задание выдаёт работодатель", code="employer_only")
        duration = data.due_at - now()
        if not MIN_DURATION <= duration <= MAX_DURATION:
            raise AppError(
                "Срок — от 10 минут до 90 дней от текущего момента",
                code="invalid_due_at",
                status_code=422,
            )
        task = await self._issue(
            employer,
            conversation,
            title=data.title,
            description=data.description,
            due_at=data.due_at,
            recurrence_days=data.recurrence_days,
            attachment_ids=data.attachment_ids,
            series_id=None,
        )
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def submit(
        self, candidate: Principal, task_id: uuid.UUID, data: TaskSubmit
    ) -> Task:
        task = await self._for_update(candidate, task_id)
        if task.candidate_id != candidate.id:
            raise ForbiddenError("Решение отправляет кандидат", code="candidate_only")
        if task.status == TaskStatus.ASSIGNED and now() > task.due_at:
            await self._expire(task)
            await self.session.commit()
        if task.status != TaskStatus.ASSIGNED:
            raise ConflictError(
                "Задание уже решено, проверено или закрыто", code=f"task_{task.status}"
            )
        submitted_at = now()
        message = await self.chat.send(
            candidate,
            task.conversation_id,
            MessageCreate(text=data.text, attachment_ids=data.attachment_ids),
            kind=MessageKind.TASK_SUBMISSION,
            task_id=task.id,
            notify_other=False,
            commit=False,
        )
        task.status = TaskStatus.SUBMITTED
        task.response_type = data.response_type
        task.submitted_at = submitted_at
        task.submission_message_id = message.id
        record_activity(
            self.session,
            task.candidate_id,
            "task_submitted",
            task.id,
            submitted_at,
            {"response_type": data.response_type, "employer_id": str(task.employer_id)},
        )
        notify(
            self.session,
            task.employer_id,
            "task.submitted",
            f"Кандидат прислал {RESPONSE_TITLES[ResponseType(data.response_type)]}",
            f"Задание «{task.title}»: ответ готов к проверке.",
            _task_link(task),
            f"task:{task.id}:submitted",
        )
        await self._publish(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def review(
        self, employer: Principal, task_id: uuid.UUID, data: TaskReview
    ) -> Task:
        task = await self._for_update(employer, task_id)
        if task.employer_id != employer.id:
            raise ForbiddenError("Проверяет работодатель", code="employer_only")
        if task.status != TaskStatus.SUBMITTED:
            raise ConflictError("Проверять пока нечего", code=f"task_{task.status}")
        reviewed_at = now()
        task.status = TaskStatus(data.result)
        task.score = data.score
        task.feedback = data.feedback
        task.reviewed_at = reviewed_at
        conversation = await self.session.get(Conversation, task.conversation_id)
        assert conversation is not None
        verdict = RESULT_TITLES[TaskStatus(task.status)]
        text = f"Задание «{task.title}»: {verdict}"
        if data.score is not None:
            text += f", оценка {data.score}/100"
        if data.feedback:
            text += f".\nКомментарий: {data.feedback}"
        await self.chat.add_system_message(
            conversation, text, f"task:{task.id}:reviewed"
        )
        record_activity(
            self.session,
            task.candidate_id,
            "task_reviewed",
            task.id,
            reviewed_at,
            {"result": data.result, "score": data.score},
        )
        notify(
            self.session,
            task.candidate_id,
            "task.reviewed",
            f"Результат задания: {verdict}",
            text,
            _task_link(task),
            f"task:{task.id}:reviewed",
        )
        await self._publish(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def cancel(self, employer: Principal, task_id: uuid.UUID) -> Task:
        task = await self._for_update(employer, task_id)
        if task.employer_id != employer.id:
            raise ForbiddenError("Отменяет работодатель", code="employer_only")
        if task.status not in (TaskStatus.ASSIGNED, TaskStatus.SUBMITTED):
            raise ConflictError("Задание уже закрыто", code=f"task_{task.status}")
        await self._close(task, TaskStatus.CANCELLED, "отменено работодателем")
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def stop_recurrence(self, employer: Principal, task_id: uuid.UUID) -> Task:
        task = await self._for_update(employer, task_id)
        if task.employer_id != employer.id:
            raise ForbiddenError("Только работодатель", code="employer_only")
        task.next_issue_at = None
        await self._publish(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def close_for_conversation(self, conversation: Conversation) -> None:
        """Диалог закрыт: открытые задания отменяются, повторы прекращаются."""
        tasks = await self.session.scalars(
            select(Task)
            .where(Task.conversation_id == conversation.id)
            .with_for_update()
        )
        for task in tasks:
            task.next_issue_at = None
            if task.status in (TaskStatus.ASSIGNED, TaskStatus.SUBMITTED):
                await self._close(
                    task, TaskStatus.CANCELLED, "закрыто вместе с перепиской"
                )

    # --- Планировщик ---------------------------------------------------------------

    async def run_scheduled(self) -> dict[str, int]:
        """Просрочка, напоминания и выдача повторяющихся заданий."""
        current = now()
        counts = {"expired": 0, "reminded": 0, "issued": 0}

        overdue = await self.session.scalars(
            select(Task)
            .where(Task.status == TaskStatus.ASSIGNED, Task.due_at < current)
            .with_for_update(skip_locked=True)
        )
        for task in overdue:
            await self._expire(task)
            counts["expired"] += 1

        remind_from = current + timedelta(hours=settings.task_reminder_hours)
        upcoming = await self.session.scalars(
            select(Task)
            .where(
                Task.status == TaskStatus.ASSIGNED,
                Task.reminded_at.is_(None),
                Task.due_at <= remind_from,
                Task.due_at > current,
            )
            .with_for_update(skip_locked=True)
        )
        for task in upcoming:
            task.reminded_at = current
            notify(
                self.session,
                task.candidate_id,
                "task.reminder",
                f"Скоро срок задания «{task.title}»",
                f"Ответ нужно отправить до {task.due_at:%d.%m.%Y %H:%M} UTC.",
                _task_link(task),
                f"task:{task.id}:reminder",
            )
            counts["reminded"] += 1

        recurring = list(
            await self.session.scalars(
                select(Task)
                .where(Task.next_issue_at.is_not(None), Task.next_issue_at <= current)
                .with_for_update(skip_locked=True)
            )
        )
        for task in recurring:
            task.next_issue_at = None
            conversation = await self.session.get(Conversation, task.conversation_id)
            if conversation is None or conversation.status != ConversationStatus.OPEN:
                continue
            employer = Principal(id=task.employer_id, email="", roles=frozenset())
            await self._issue(
                employer,
                conversation,
                title=task.title,
                description=task.description,
                due_at=current + (task.due_at - task.created_at),
                recurrence_days=task.recurrence_days,
                attachment_ids=[],
                series_id=task.series_id or task.id,
            )
            counts["issued"] += 1

        await self.session.commit()
        if any(counts.values()):
            logger.info("Task scheduler: %s", counts)
        return counts

    # --- Внутреннее ------------------------------------------------------------------

    async def _issue(
        self,
        employer: Principal,
        conversation: Conversation,
        *,
        title: str,
        description: str,
        due_at: object,
        recurrence_days: int | None,
        attachment_ids: list[uuid.UUID],
        series_id: uuid.UUID | None,
    ) -> Task:
        issued_at = now()
        task = Task(
            conversation_id=conversation.id,
            employer_id=conversation.employer_id,
            candidate_id=conversation.candidate_id,
            title=title,
            description=description,
            due_at=due_at,
            status=TaskStatus.ASSIGNED,
            recurrence_days=recurrence_days,
            next_issue_at=(
                issued_at + timedelta(days=recurrence_days) if recurrence_days else None
            ),
            series_id=series_id,
        )
        self.session.add(task)
        await self.session.flush()
        await self.chat.send(
            employer,
            conversation.id,
            MessageCreate(
                text=f"{title}\n\n{description}",
                attachment_ids=attachment_ids,
                client_id=f"task:{task.id}",
            ),
            kind=MessageKind.TASK,
            task_id=task.id,
            notify_other=False,
            commit=False,
        )
        record_activity(
            self.session,
            task.candidate_id,
            "task_assigned",
            task.id,
            issued_at,
            {"employer_id": str(task.employer_id)},
        )
        notify(
            self.session,
            task.candidate_id,
            "task.assigned",
            f"Новое задание от {conversation.company_name}",
            f"«{title}». Решите задачу или предложите подход до "
            f"{task.due_at:%d.%m.%Y %H:%M} UTC.",
            _task_link(task),
            f"task:{task.id}:assigned",
        )
        await self._publish(task)
        return task

    async def _for_update(self, principal: Principal, task_id: uuid.UUID) -> Task:
        await self.get(principal, task_id)
        task = await self.session.scalar(
            select(Task).where(Task.id == task_id).with_for_update()
        )
        assert task is not None
        return task

    async def _expire(self, task: Task) -> None:
        await self._close(task, TaskStatus.EXPIRED, "срок истёк, ответ не получен")
        record_activity(self.session, task.candidate_id, "task_expired", task.id, now())

    async def _close(self, task: Task, status: TaskStatus, reason: str) -> None:
        task.status = status
        task.next_issue_at = (
            None if status == TaskStatus.CANCELLED else task.next_issue_at
        )
        conversation = await self.session.get(Conversation, task.conversation_id)
        assert conversation is not None
        text = f"Задание «{task.title}» {reason}."
        await self.chat.add_system_message(
            conversation, text, f"task:{task.id}:{status}"
        )
        notify(
            self.session,
            task.candidate_id,
            f"task.{status}",
            f"Задание «{task.title}»: {reason}",
            text,
            _task_link(task),
            f"task:{task.id}:{status}",
            email=status == TaskStatus.EXPIRED,
        )
        await self._publish(task)

    async def _publish(self, task: Task) -> None:
        await realtime.publish(
            self.session,
            [task.candidate_id, task.employer_id],
            "task.updated",
            task_id=task.id,
        )
