"""Управление контентом тестов: создание, редактирование, импорт и экспорт.

Вопросы и ответы хранятся только в БД сервиса. В репозитории их нет:
наполнение — через админский API или импорт пакета (``TestPack``) из файла,
который хранится вне git.
"""

import uuid

from benefit_common.errors import ConflictError, NotFoundError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Assessment, AssessmentTask, Attempt
from app.schemas.content import (
    AdminTestDetail,
    AdminTestSummary,
    ImportReport,
    TaskIn,
    TestIn,
    TestPack,
)

TEST_FIELDS = (
    "title",
    "description",
    "specialization",
    "grade",
    "time_limit_seconds",
    "tasks_per_attempt",
    "is_active",
)
TASK_FIELDS = (
    "kind",
    "prompt",
    "code",
    "correct",
    "points",
    "time_limit_seconds",
    "skills",
    "explanation",
    "is_active",
)


# Админка управляет только тестами платформы; тесты работодателей приватны.
PLATFORM = Assessment.owner_id.is_(None)


def _not_found() -> NotFoundError:
    return NotFoundError("Тест не найден", code="assessment_not_found")


def to_test_in(assessment: Assessment) -> TestIn:
    return TestIn(
        slug=assessment.slug,
        **{field: getattr(assessment, field) for field in TEST_FIELDS},
        tasks=[
            TaskIn(
                key=task.key,
                options=task.options,
                **{field: getattr(task, field) for field in TASK_FIELDS},
            )
            for task in assessment.tasks
        ],
    )


class ContentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _load(self, assessment_id: uuid.UUID) -> Assessment:
        assessment = await self.session.scalar(
            select(Assessment)
            .where(Assessment.id == assessment_id, PLATFORM)
            .options(selectinload(Assessment.tasks))
        )
        if assessment is None:
            raise _not_found()
        return assessment

    async def summaries(self) -> list[AdminTestSummary]:
        attempts = dict(
            (
                await self.session.execute(
                    select(Attempt.assessment_id, func.count()).group_by(
                        Attempt.assessment_id
                    )
                )
            ).all()
        )
        assessments = await self.session.scalars(
            select(Assessment)
            .where(PLATFORM)
            .options(selectinload(Assessment.tasks))
            .order_by(Assessment.specialization, Assessment.grade)
        )
        return [
            AdminTestSummary(
                id=a.id,
                slug=a.slug,
                title=a.title,
                specialization=a.specialization,
                grade=a.grade,
                is_active=a.is_active,
                tasks_total=len(a.tasks),
                tasks_active=sum(1 for t in a.tasks if t.is_active),
                attempts=attempts.get(a.id, 0),
                updated_at=a.updated_at,
                updated_by=a.updated_by,
            )
            for a in assessments
        ]

    async def get(self, assessment_id: uuid.UUID) -> AdminTestDetail:
        assessment = await self._load(assessment_id)
        return AdminTestDetail(
            **to_test_in(assessment).model_dump(),
            id=assessment.id,
            updated_at=assessment.updated_at,
            updated_by=assessment.updated_by,
        )

    async def create(self, data: TestIn, actor: uuid.UUID) -> AdminTestDetail:
        exists = await self.session.scalar(
            select(Assessment.id).where(Assessment.slug == data.slug)
        )
        if exists is not None:
            raise ConflictError("Тест с таким slug уже есть", code="slug_taken")
        assessment = Assessment(slug=data.slug, tasks=[])
        self.session.add(assessment)
        await self._apply(assessment, data, actor)
        await self.session.commit()
        return await self.get(assessment.id)

    async def replace(
        self, assessment_id: uuid.UUID, data: TestIn, actor: uuid.UUID
    ) -> AdminTestDetail:
        assessment = await self._load(assessment_id)
        if data.slug != assessment.slug:
            raise ConflictError("slug теста менять нельзя", code="slug_immutable")
        await self._apply(assessment, data, actor)
        await self.session.commit()
        return await self.get(assessment.id)

    async def set_active(
        self, assessment_id: uuid.UUID, is_active: bool, actor: uuid.UUID
    ) -> AdminTestDetail:
        assessment = await self._load(assessment_id)
        assessment.is_active = is_active
        assessment.updated_by = actor
        await self.session.commit()
        return await self.get(assessment.id)

    async def import_pack(
        self, pack: TestPack, actor: uuid.UUID | None, *, skip_existing: bool
    ) -> ImportReport:
        report = ImportReport(created=[], updated=[], skipped=[])
        for data in pack.tests:
            assessment = await self.session.scalar(
                select(Assessment)
                .where(Assessment.slug == data.slug, PLATFORM)
                .options(selectinload(Assessment.tasks))
            )
            if assessment is not None and skip_existing:
                report.skipped.append(data.slug)
                continue
            if assessment is None:
                assessment = Assessment(slug=data.slug, tasks=[])
                self.session.add(assessment)
                report.created.append(data.slug)
            else:
                report.updated.append(data.slug)
            await self._apply(assessment, data, actor)
        await self.session.commit()
        return report

    async def export(self, ids: list[uuid.UUID] | None = None) -> TestPack:
        query = (
            select(Assessment).where(PLATFORM).options(selectinload(Assessment.tasks))
        )
        if ids:
            query = query.where(Assessment.id.in_(ids))
        assessments = list(await self.session.scalars(query.order_by(Assessment.slug)))
        if not assessments:
            raise _not_found()
        return TestPack(tests=[to_test_in(a) for a in assessments])

    async def apply(
        self, assessment: Assessment, data: TestIn, actor: uuid.UUID | None
    ) -> None:
        await self._apply(assessment, data, actor)

    async def _apply(
        self, assessment: Assessment, data: TestIn, actor: uuid.UUID | None
    ) -> None:
        """Обновляет тест и банк задач (сопоставление задач по ``key``).

        Задачи, которых нет в новых данных, деактивируются, а не удаляются:
        на них ссылаются прошлые попытки кандидатов.
        """
        for field in TEST_FIELDS:
            setattr(assessment, field, getattr(data, field))
        assessment.updated_by = actor

        existing = {task.key: task for task in assessment.tasks}
        for position, item in enumerate(data.tasks, start=1):
            task = existing.pop(item.key, None)
            if task is None:
                task = AssessmentTask(key=item.key)
                assessment.tasks.append(task)
            task.position = position
            task.options = [option.model_dump() for option in item.options]
            for field in TASK_FIELDS:
                setattr(task, field, getattr(item, field))
        for task in existing.values():
            task.is_active = False
        await self.session.flush()
