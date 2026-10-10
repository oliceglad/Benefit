"""Тесты работодателей и их отправка кандидатам.

Работодатель создаёт свой тест (видит и редактирует его только он) и
отправляет его кандидату в переписке. Кандидат проходит тест тем же
механизмом, что и тесты платформы (время каждой задачи, баллы), но грейд
такой тест не подтверждает: результат получает работодатель.
"""

import uuid
from datetime import timedelta
from typing import Any, Protocol

from benefit_common.errors import AppError, ConflictError, NotFoundError
from benefit_common.internal import InternalClient, raise_for_client_error
from benefit_common.security import Principal
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import (
    Assessment,
    AssignmentStatus,
    Attempt,
    AttemptStatus,
    AttemptTask,
    TestAssignment,
)
from app.schemas.content import TestIn
from app.schemas.employer import (
    AnswerReview,
    AssignmentCreate,
    AssignmentResponse,
    AssignmentResult,
    AssignmentTest,
    EmployerAssignmentResponse,
    EmployerTestDetail,
    EmployerTestIn,
    EmployerTestSummary,
)
from app.services import clock
from app.services.assignment_events import activity, chat_message, notify
from app.services.attempts import AttemptService
from app.services.content import ContentService, to_test_in

MIN_DUE = timedelta(minutes=10)
MAX_DUE = timedelta(days=30)


class ChatDirectory(Protocol):
    async def conversation(self, conversation_id: uuid.UUID) -> dict[str, Any] | None:
        """Диалог из chat-service или ``None``, если его нет."""
        ...


class ChatServiceClient:
    def __init__(self) -> None:
        self.client = InternalClient(settings.chat_service_url, service="chat")

    async def conversation(self, conversation_id: uuid.UUID) -> dict[str, Any] | None:
        response = await self.client.get(
            f"/internal/v1/conversations/{conversation_id}"
        )
        if response.status_code == 404:
            return None
        raise_for_client_error(response)
        return response.json()


def get_chat_directory() -> ChatDirectory:
    return ChatServiceClient()


def _test_not_found() -> NotFoundError:
    return NotFoundError("Тест не найден", code="assessment_not_found")


def _assignment_not_found() -> NotFoundError:
    return NotFoundError("Тест не найден", code="assignment_not_found")


class EmployerTestService:
    def __init__(
        self, session: AsyncSession, chat: ChatDirectory, attempts: AttemptService
    ) -> None:
        self.session = session
        self.chat = chat
        self.attempts = attempts
        self.content = ContentService(session)

    # --- Тесты работодателя -----------------------------------------------------

    async def _own_test(self, employer: Principal, test_id: uuid.UUID) -> Assessment:
        assessment = await self.session.scalar(
            select(Assessment)
            .where(Assessment.id == test_id)
            .options(selectinload(Assessment.tasks))
        )
        # Чужие тесты и тесты платформы неотличимы от несуществующих.
        if assessment is None or assessment.owner_id != employer.id:
            raise _test_not_found()
        return assessment

    async def list_tests(self, employer: Principal) -> list[EmployerTestSummary]:
        counts = dict(
            (
                await self.session.execute(
                    select(TestAssignment.assessment_id, func.count())
                    .where(TestAssignment.employer_id == employer.id)
                    .group_by(TestAssignment.assessment_id)
                )
            ).all()
        )
        tests = await self.session.scalars(
            select(Assessment)
            .where(Assessment.owner_id == employer.id)
            .options(selectinload(Assessment.tasks))
            .order_by(Assessment.created_at.desc())
        )
        return [
            EmployerTestSummary(
                id=t.id,
                title=t.title,
                specialization=t.specialization,
                grade=t.grade,
                is_active=t.is_active,
                tasks_total=sum(1 for task in t.tasks if task.is_active),
                tasks_per_attempt=t.tasks_per_attempt,
                time_limit_seconds=t.time_limit_seconds,
                assignments=counts.get(t.id, 0),
                updated_at=t.updated_at,
            )
            for t in tests
        ]

    async def get_test(
        self, employer: Principal, test_id: uuid.UUID
    ) -> EmployerTestDetail:
        assessment = await self._own_test(employer, test_id)
        data = to_test_in(assessment)
        return EmployerTestDetail(
            **data.model_dump(exclude={"slug", "is_active", "kind", "skill", "levels"}),
            id=assessment.id,
            is_active=assessment.is_active,
            updated_at=assessment.updated_at,
        )

    async def create_test(
        self, employer: Principal, data: EmployerTestIn
    ) -> EmployerTestDetail:
        assessment = Assessment(
            slug=f"employer-{uuid.uuid4().hex[:16]}", owner_id=employer.id, tasks=[]
        )
        self.session.add(assessment)
        await self.content.apply(
            assessment, self._to_test_in(assessment, data), employer.id
        )
        await self.session.commit()
        return await self.get_test(employer, assessment.id)

    async def replace_test(
        self, employer: Principal, test_id: uuid.UUID, data: EmployerTestIn
    ) -> EmployerTestDetail:
        """Задачи сопоставляются по ``key``; убранные — деактивируются
        (на них ссылаются уже пройденные попытки)."""
        assessment = await self._own_test(employer, test_id)
        await self.content.apply(
            assessment, self._to_test_in(assessment, data), employer.id
        )
        await self.session.commit()
        return await self.get_test(employer, assessment.id)

    async def set_active(
        self, employer: Principal, test_id: uuid.UUID, is_active: bool
    ) -> EmployerTestDetail:
        """Архивный тест нельзя отправить; уже отправленные остаются в силе."""
        assessment = await self._own_test(employer, test_id)
        assessment.is_active = is_active
        await self.session.commit()
        return await self.get_test(employer, assessment.id)

    @staticmethod
    def _to_test_in(assessment: Assessment, data: EmployerTestIn) -> TestIn:
        return TestIn(
            slug=assessment.slug,
            is_active=assessment.is_active if assessment.id else True,
            **data.model_dump(),
        )

    # --- Отправка теста кандидату ---------------------------------------------------

    async def assign(
        self, employer: Principal, test_id: uuid.UUID, data: AssignmentCreate
    ) -> EmployerAssignmentResponse:
        assessment = await self._own_test(employer, test_id)
        if not assessment.is_active:
            raise ConflictError("Тест в архиве", code="assessment_archived")
        conversation = await self.chat.conversation(data.conversation_id)
        if conversation is None or conversation["employer_id"] != str(employer.id):
            raise NotFoundError("Переписка не найдена", code="conversation_not_found")
        if conversation["status"] != "open":
            raise ConflictError(
                "Переписка закрыта: кандидат отклонил приглашение",
                code="conversation_closed",
            )
        until = data.due_at - clock.now()
        if not MIN_DUE <= until <= MAX_DUE:
            raise AppError(
                "Срок — от 10 минут до 30 дней", code="invalid_due_at", status_code=422
            )

        assignment = TestAssignment(
            assessment_id=assessment.id,
            employer_id=employer.id,
            candidate_id=uuid.UUID(conversation["candidate_id"]),
            conversation_id=data.conversation_id,
            company_name=conversation["company_name"],
            vacancy_title=conversation["vacancy_title"],
            message=data.message,
            due_at=data.due_at,
            status=AssignmentStatus.ASSIGNED,
        )
        self.session.add(assignment)
        await self.session.flush()
        assignment.assessment = assessment
        minutes = assessment.time_limit_seconds // 60
        text = (
            f"Тест «{assessment.title}»: {assessment.tasks_per_attempt} задач, "
            f"{minutes} мин. Начать до {data.due_at:%d.%m.%Y %H:%M} UTC."
        )
        if data.message:
            text += f"\n\n{data.message}"
        chat_message(
            self.session,
            assignment,
            "assigned",
            text,
            kind="assessment",
            data={
                "title": assessment.title,
                "tasks": assessment.tasks_per_attempt,
                "time_limit_seconds": assessment.time_limit_seconds,
                "due_at": data.due_at.isoformat(),
            },
        )
        notify(
            self.session,
            assignment,
            assignment.candidate_id,
            "assigned",
            f"{assignment.company_name} прислал тест",
            text,
            employer=False,
        )
        await self.session.commit()
        return await self._employer_view(assignment)

    async def employer_assignments(
        self, employer: Principal, test_id: uuid.UUID | None = None
    ) -> list[AssignmentResponse]:
        query = select(TestAssignment).where(TestAssignment.employer_id == employer.id)
        if test_id is not None:
            query = query.where(TestAssignment.assessment_id == test_id)
        return await self._views(query)

    async def employer_assignment(
        self, employer: Principal, assignment_id: uuid.UUID
    ) -> EmployerAssignmentResponse:
        assignment = await self._assignment(assignment_id)
        if assignment.employer_id != employer.id:
            raise _assignment_not_found()
        return await self._employer_view(assignment)

    async def cancel(
        self, employer: Principal, assignment_id: uuid.UUID
    ) -> EmployerAssignmentResponse:
        assignment = await self._assignment(assignment_id, lock=True)
        if assignment.employer_id != employer.id:
            raise _assignment_not_found()
        self._ensure_assigned(assignment)
        assignment.status = AssignmentStatus.CANCELLED
        chat_message(
            self.session,
            assignment,
            "cancelled",
            f"Работодатель отменил тест «{assignment.assessment.title}».",
        )
        await self.session.commit()
        return await self._employer_view(assignment)

    # --- Кандидат ---------------------------------------------------------------

    async def candidate_assignments(
        self, candidate: Principal
    ) -> list[AssignmentResponse]:
        await self.expire_overdue(candidate_id=candidate.id)
        return await self._views(
            select(TestAssignment).where(TestAssignment.candidate_id == candidate.id)
        )

    async def candidate_assignment(
        self, candidate: Principal, assignment_id: uuid.UUID
    ) -> AssignmentResponse:
        assignment = await self._candidate_assignment(candidate, assignment_id)
        return await self._view(assignment)

    async def start(self, candidate: Principal, assignment_id: uuid.UUID) -> Any:
        assignment = await self._candidate_assignment(
            candidate, assignment_id, lock=True
        )
        self._ensure_assigned(assignment)
        if await self.attempts.active_attempt(candidate.id) is not None:
            raise ConflictError(
                "Сначала завершите начатый тест", code="attempt_in_progress"
            )
        assessment = await self.session.scalar(
            select(Assessment)
            .where(Assessment.id == assignment.assessment_id)
            .options(selectinload(Assessment.tasks))
        )
        assert assessment is not None
        attempt = self.attempts.new_attempt(
            candidate,
            assessment,
            skills=set(),
            survey={},
            claimed_grade=None,
            assignment_id=assignment.id,
        )
        self.session.add(attempt)
        assignment.status = AssignmentStatus.IN_PROGRESS
        assignment.started_at = attempt.started_at
        await self.session.commit()
        return await self.attempts.get(candidate, attempt.id)

    async def decline(
        self, candidate: Principal, assignment_id: uuid.UUID
    ) -> AssignmentResponse:
        assignment = await self._candidate_assignment(
            candidate, assignment_id, lock=True
        )
        self._ensure_assigned(assignment)
        assignment.status = AssignmentStatus.DECLINED
        title = assignment.assessment.title
        chat_message(
            self.session,
            assignment,
            "declined",
            f"Кандидат отказался от теста «{title}».",
        )
        notify(
            self.session,
            assignment,
            assignment.employer_id,
            "declined",
            f"Кандидат отказался от теста «{title}»",
            "Можно обсудить это в переписке.",
            employer=True,
        )
        await self.session.commit()
        return await self._view(assignment)

    async def expire_overdue(self, candidate_id: uuid.UUID | None = None) -> int:
        """Тест так и не начат до срока — приглашение пройти его истекает."""
        query = (
            select(TestAssignment)
            .where(
                TestAssignment.status == AssignmentStatus.ASSIGNED,
                TestAssignment.due_at < clock.now(),
            )
            .options(selectinload(TestAssignment.assessment))
            .with_for_update(of=TestAssignment, skip_locked=True)
        )
        if candidate_id is not None:
            query = query.where(TestAssignment.candidate_id == candidate_id)
        expired = list(await self.session.scalars(query))
        for assignment in expired:
            assignment.status = AssignmentStatus.EXPIRED
            title = assignment.assessment.title
            chat_message(
                self.session,
                assignment,
                "expired",
                f"Срок начала теста «{title}» истёк.",
            )
            notify(
                self.session,
                assignment,
                assignment.employer_id,
                "expired",
                f"Кандидат не начал тест «{title}»",
                "Срок начала теста истёк. Можно отправить тест повторно.",
                employer=True,
            )
            activity(self.session, assignment, "employer_test_expired", clock.now())
        if expired:
            await self.session.commit()
        return len(expired)

    # --- Внутреннее -------------------------------------------------------------

    async def _assignment(
        self, assignment_id: uuid.UUID, *, lock: bool = False
    ) -> TestAssignment:
        query = (
            select(TestAssignment)
            .where(TestAssignment.id == assignment_id)
            .options(selectinload(TestAssignment.assessment))
        )
        if lock:
            query = query.with_for_update(of=TestAssignment)
        assignment = await self.session.scalar(query)
        if assignment is None:
            raise _assignment_not_found()
        return assignment

    async def _candidate_assignment(
        self, candidate: Principal, assignment_id: uuid.UUID, *, lock: bool = False
    ) -> TestAssignment:
        await self.expire_overdue(candidate_id=candidate.id)
        assignment = await self._assignment(assignment_id, lock=lock)
        if assignment.candidate_id != candidate.id:
            raise _assignment_not_found()
        return assignment

    @staticmethod
    def _ensure_assigned(assignment: TestAssignment) -> None:
        if assignment.status != AssignmentStatus.ASSIGNED:
            raise ConflictError(
                "Тест уже начат, завершён или закрыт",
                code=f"assignment_{assignment.status}",
            )

    async def _attempt(self, assignment: TestAssignment) -> Attempt | None:
        return await self.session.scalar(
            select(Attempt)
            .where(Attempt.assignment_id == assignment.id)
            .options(selectinload(Attempt.tasks).selectinload(AttemptTask.task))
            .order_by(Attempt.started_at.desc())
            .limit(1)
        )

    async def _views(self, query: Any) -> list[AssignmentResponse]:
        assignments = await self.session.scalars(
            query.options(selectinload(TestAssignment.assessment)).order_by(
                TestAssignment.created_at.desc()
            )
        )
        return [await self._view(a) for a in assignments]

    async def _view(self, assignment: TestAssignment) -> AssignmentResponse:
        # Только колонки: связи уже загружены, их refresh не трогает.
        await self.session.refresh(
            assignment, ["status", "created_at", "started_at", "completed_at"]
        )
        assessment = assignment.assessment
        attempt = await self._attempt(assignment)
        result = None
        if attempt is not None:
            result = AssignmentResult(
                attempt_id=attempt.id,
                status=attempt.status,
                score=attempt.score,
                max_score=attempt.max_score,
                percent=attempt.percent,
                duration_seconds=attempt.duration_seconds,
            )
        return AssignmentResponse(
            id=assignment.id,
            status=assignment.status,
            test=AssignmentTest(
                title=assessment.title,
                description=assessment.description,
                specialization=assessment.specialization,
                grade=assessment.grade,
                time_limit_seconds=assessment.time_limit_seconds,
                tasks_per_attempt=assessment.tasks_per_attempt,
            ),
            employer_id=assignment.employer_id,
            candidate_id=assignment.candidate_id,
            conversation_id=assignment.conversation_id,
            company_name=assignment.company_name,
            vacancy_title=assignment.vacancy_title,
            message=assignment.message,
            due_at=assignment.due_at,
            created_at=assignment.created_at,
            started_at=assignment.started_at,
            completed_at=assignment.completed_at,
            result=result,
        )

    async def _employer_view(
        self, assignment: TestAssignment
    ) -> EmployerAssignmentResponse:
        """Для автора теста: ответы кандидата и правильные ответы.

        Пока попытка идёт, ответы не показываются.
        """
        view = await self._view(assignment)
        attempt = await self._attempt(assignment)
        answers = []
        if attempt is not None and attempt.status != AttemptStatus.IN_PROGRESS:
            answers = [
                AnswerReview(
                    position=item.position,
                    kind=item.task.kind,
                    prompt=item.task.prompt,
                    code=item.task.code,
                    options=item.task.options,
                    correct=item.task.correct,
                    answer=item.answer,
                    is_correct=item.is_correct,
                    points_awarded=item.points_awarded,
                    max_points=item.max_points,
                    time_spent_seconds=item.time_spent_seconds,
                    time_limit_seconds=item.time_limit_seconds,
                    timed_out=item.timed_out,
                    skipped=item.skipped,
                )
                for item in attempt.tasks
            ]
        return EmployerAssignmentResponse(**view.model_dump(), answers=answers)
