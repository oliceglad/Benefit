"""События по тестам работодателей: сообщения в переписку, уведомления,
активность кандидата. Доставка — через outbox."""

import uuid
from datetime import datetime
from typing import Any

from benefit_common.outbox import enqueue
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssignmentStatus, Attempt, OutboxMessage, TestAssignment
from app.services import clock
from app.services.delivery import CANDIDATE_ACTIVITY, CHAT_MESSAGE, NOTIFICATION


def assignment_link(assignment: TestAssignment, *, employer: bool) -> str:
    side = "employer/assignments" if employer else "assignments"
    return f"/assessments/{side}/{assignment.id}"


def chat_message(
    session: AsyncSession,
    assignment: TestAssignment,
    event: str,
    text: str,
    *,
    kind: str = "system",
    data: dict[str, Any] | None = None,
) -> None:
    enqueue(
        session,
        OutboxMessage,
        CHAT_MESSAGE,
        {
            "conversation_id": str(assignment.conversation_id),
            "kind": kind,
            "sender_id": str(assignment.employer_id) if kind == "assessment" else None,
            "text": text,
            "data": {"assignment_id": str(assignment.id), **(data or {})},
            "client_id": f"assignment:{assignment.id}:{event}",
        },
    )


def notify(
    session: AsyncSession,
    assignment: TestAssignment,
    user_id: uuid.UUID,
    event: str,
    title: str,
    body: str,
    *,
    employer: bool,
) -> None:
    enqueue(
        session,
        OutboxMessage,
        NOTIFICATION,
        {
            "user_id": str(user_id),
            "type": f"employer_test.{event}",
            "title": title,
            "body": body,
            "link": assignment_link(assignment, employer=employer),
            "data": {"assignment_id": str(assignment.id)},
            "email": True,
            "dedup_key": f"assignment:{assignment.id}:{event}:{user_id}",
        },
    )


def activity(
    session: AsyncSession,
    assignment: TestAssignment,
    kind: str,
    occurred_at: datetime,
    data: dict[str, Any] | None = None,
) -> None:
    enqueue(
        session,
        OutboxMessage,
        CANDIDATE_ACTIVITY,
        {
            "user_id": str(assignment.candidate_id),
            "kind": kind,
            "ref_id": str(assignment.id),
            "occurred_at": occurred_at.isoformat(),
            "data": data or {},
        },
    )


def _duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes} мин {secs:02d} с"


async def publish_assignment_result(session: AsyncSession, attempt: Attempt) -> None:
    """Тест работодателя завершён: итог — в переписку и работодателю."""
    assignment = await session.get(TestAssignment, attempt.assignment_id)
    if assignment is None:
        return
    assignment.status = AssignmentStatus.COMPLETED
    assignment.completed_at = attempt.finished_at or clock.now()
    title = attempt.assessment.title
    summary = (
        f"{attempt.percent:g}% ({attempt.score:g} из {attempt.max_score} баллов), "
        f"время {_duration(attempt.duration_seconds or 0)}"
    )
    chat_message(
        session,
        assignment,
        "completed",
        f"Кандидат прошёл тест «{title}»: {summary}.",
        data={"attempt_id": str(attempt.id), "percent": attempt.percent},
    )
    notify(
        session,
        assignment,
        assignment.employer_id,
        "completed",
        f"Кандидат прошёл тест «{title}»",
        f"Результат: {summary}. Подробности — по ответам и времени на каждую задачу.",
        employer=True,
    )
    activity(
        session,
        assignment,
        "employer_test_completed",
        assignment.completed_at,
        {"percent": attempt.percent, "employer_id": str(assignment.employer_id)},
    )
