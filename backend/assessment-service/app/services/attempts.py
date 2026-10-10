"""Прохождение тестирования: опрос, попытка, задачи с таймингом, итог."""

import logging
import random
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from benefit_common.dictionaries import (
    GRADE_ORDER,
    GRADE_TITLES,
    INDUSTRY_TITLES,
    ROLE_TITLES,
    Grade,
    Industry,
    ITRole,
)
from benefit_common.errors import AppError, ConflictError, NotFoundError
from benefit_common.outbox import enqueue
from benefit_common.security import Principal
from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import (
    Assessment,
    AssessmentKind,
    AssessmentTask,
    Attempt,
    AttemptStatus,
    AttemptTask,
    OutboxMessage,
    Outcome,
)
from app.schemas.assessment import (
    AnswerRequest,
    AnswerResponse,
    AssessmentInfo,
    AssessmentStatus,
    AttemptResponse,
    AttemptResult,
    AttemptSummary,
    CooldownInfo,
    LevelInfo,
    Option,
    SkillScore,
    SkillTestOption,
    SpecializationOption,
    SurveyAnswers,
    SurveyOptions,
    SurveyPrefill,
    TaskOption,
    TaskResult,
    TaskView,
    VerifiedCategory,
    VerifiedSkill,
)
from app.services import clock
from app.services.assignment_events import publish_assignment_result
from app.services.candidates import CandidateDirectory
from app.services.delivery import CANDIDATE_ASSESSMENT, CANDIDATE_SKILL, NOTIFICATION
from app.services.scoring import evaluate, evaluate_level, score, validate_answer

logger = logging.getLogger(__name__)

FINISHED = (AttemptStatus.COMPLETED, AttemptStatus.EXPIRED)


def _grace() -> timedelta:
    return timedelta(seconds=settings.time_grace_seconds)


def _attempt_query() -> Any:
    return select(Attempt).options(
        selectinload(Attempt.assessment),
        selectinload(Attempt.tasks).selectinload(AttemptTask.task),
    )


def select_tasks(
    tasks: list[AssessmentTask], skills: set[str], count: int, rng: random.Random
) -> list[AssessmentTask]:
    """Сначала задачи по навыкам кандидата, остальное — из общего банка."""
    known = {s.lower() for s in skills}
    matching = [t for t in tasks if known & {s.lower() for s in t.skills}]
    other = [t for t in tasks if t not in matching]
    rng.shuffle(matching)
    rng.shuffle(other)
    chosen = (matching + other)[:count]
    # Внутри попытки — в порядке банка (от простых к сложным).
    return sorted(chosen, key=lambda t: t.position)


def level_of(attempt: Attempt) -> LevelInfo | None:
    """Подтверждённый уровень навыка по шкале теста попытки."""
    if attempt.confirmed_level is None:
        return None
    for level in attempt.assessment.levels:
        if level["id"] == attempt.confirmed_level:
            return LevelInfo(**level)
    return None


def _level_rank(attempt: Attempt) -> int:
    ids = [level["id"] for level in attempt.assessment.levels]
    return ids.index(attempt.confirmed_level) if attempt.confirmed_level in ids else -1


def _retry(available_at: datetime | None) -> str:
    return (
        f" Повторить тест можно с {available_at:%d.%m.%Y %H:%M} UTC."
        if available_at
        else ""
    )


def skill_result_message(attempt: Attempt, available_at: datetime | None) -> str:
    level = level_of(attempt)
    if level is not None:
        return (
            f"{attempt.skill}: подтверждён уровень {level.title} "
            f"({attempt.percent:g}%). Работодатели видят отметку в профиле."
        )
    first = attempt.assessment.levels[0]
    return (
        f"{attempt.skill}: уровень пока не подтверждён — {attempt.percent:g}% "
        f"при пороге {first['min_percent']:g}% для {first['title']}."
        + _retry(available_at)
    )


def result_message(attempt: Attempt, available_at: datetime | None) -> str:
    if attempt.skill is not None:
        return skill_result_message(attempt, available_at)
    target = GRADE_TITLES[Grade(attempt.target_grade)]
    if attempt.outcome == Outcome.EXCEEDED:
        confirmed = GRADE_TITLES[Grade(attempt.confirmed_grade)]
        return (
            f"Отличный результат — {attempt.percent:g}%. Это выше уровня {target}: "
            f"в профиле показан подтверждённый грейд {confirmed}."
        )
    if attempt.outcome == Outcome.CONFIRMED:
        return (
            f"Грейд {target} подтверждён ({attempt.percent:g}%). "
            "Работодатели видят отметку о подтверждении."
        )
    return (
        f"Грейд {target} пока не подтверждён: {attempt.percent:g}% при пороге "
        f"{settings.pass_percent:g}%. В профиле остаётся заявленный грейд "
        f"с пометкой «не подтверждён»." + _retry(available_at)
    )


class AttemptService:
    def __init__(self, session: AsyncSession, candidates: CandidateDirectory) -> None:
        self.session = session
        self.candidates = candidates

    # --- Опрос и каталог -----------------------------------------------------

    async def catalog(self, kind: AssessmentKind | None = None) -> list[Assessment]:
        query = select(Assessment).where(
            Assessment.is_active, Assessment.owner_id.is_(None)
        )
        if kind is not None:
            query = query.where(Assessment.kind == kind)
        result = await self.session.scalars(
            query.order_by(
                Assessment.kind,
                Assessment.specialization,
                Assessment.grade,
                Assessment.skill,
            )
        )
        return list(result)

    async def survey(self, principal: Principal) -> SurveyOptions:
        catalog = await self.catalog(AssessmentKind.GRADE)
        grades_by_role: dict[str, list[Grade]] = defaultdict(list)
        for assessment in catalog:
            grades_by_role[assessment.specialization].append(Grade(assessment.grade))

        snapshot = None
        try:
            snapshot = await self.candidates.snapshot(principal.id)
        except AppError:
            # Предзаполнение — удобство: без candidate-service опрос работает.
            logger.warning("Candidate snapshot unavailable for survey prefill")
        prefill = None
        if snapshot is not None:
            roles = snapshot.get("roles") or []
            prefill = SurveyPrefill(
                industry=snapshot.get("industry"),
                specialization=roles[0] if roles else None,
                claimed_grade=snapshot.get("grade"),
                years_of_experience=round(
                    (snapshot.get("total_experience_months") or 0) / 12, 1
                ),
                skills=[s["name"] for s in snapshot.get("skills") or []],
            )

        return SurveyOptions(
            industries=[Option(id=k, title=v) for k, v in INDUSTRY_TITLES.items()],
            specializations=[
                SpecializationOption(
                    id=role,
                    title=ROLE_TITLES[role],
                    grades=sorted(grades_by_role.get(role, []), key=GRADE_ORDER.get),
                )
                for role in ITRole
            ],
            grades=[Option(id=k, title=v) for k, v in GRADE_TITLES.items()],
            prefill=prefill,
            cooldowns=await self._cooldowns(principal.id),
            pass_percent=settings.pass_percent,
            exceed_percent=settings.exceed_percent,
        )

    # --- Попытка ---------------------------------------------------------------

    async def start(
        self, principal: Principal, survey: SurveyAnswers
    ) -> AttemptResponse:
        await self.expire_overdue(user_id=principal.id)
        active = await self._active_attempt(principal.id)
        if active is not None:
            raise ConflictError(
                "Сначала завершите начатый тест", code="attempt_in_progress"
            )
        for cooldown in await self._cooldowns(principal.id):
            if cooldown.specialization == survey.specialization:
                raise AppError(
                    "Повторно пройти тест по этой специализации можно "
                    f"с {cooldown.available_at:%d.%m.%Y %H:%M} UTC",
                    code="attempt_cooldown",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        assessment = await self.session.scalar(
            select(Assessment)
            .where(
                Assessment.is_active,
                Assessment.owner_id.is_(None),
                Assessment.kind == AssessmentKind.GRADE,
                Assessment.specialization == survey.specialization,
                Assessment.grade == survey.target_grade,
            )
            .options(selectinload(Assessment.tasks))
        )
        if assessment is None:
            raise NotFoundError(
                "Для этой специализации и грейда тест пока не создан",
                code="assessment_not_found",
            )

        snapshot = await self.candidates.snapshot(principal.id)
        if snapshot is None:
            raise ConflictError(
                "Сначала создайте профиль кандидата", code="profile_required"
            )

        skills = set(survey.skills) | {s["name"] for s in snapshot.get("skills") or []}
        attempt = self.new_attempt(
            principal,
            assessment,
            skills=skills,
            survey=survey.model_dump(mode="json"),
            claimed_grade=snapshot.get("grade"),
        )
        self.session.add(attempt)
        await self.session.commit()
        return await self.view(await self._load(principal, attempt.id))

    # --- Тесты на навыки ----------------------------------------------------------

    async def skill_tests(self, principal: Principal) -> list[SkillTestOption]:
        """Каталог тестов на навыки с текущим уровнем и ограничением повтора."""
        verified = {
            v.skill.lower(): v for v in await self._verified_skills(principal.id)
        }
        cooldowns = await self._skill_cooldowns(principal.id)
        return [
            SkillTestOption(
                test=AssessmentInfo.model_validate(test),
                verified=verified.get((test.skill or "").lower()),
                available_at=cooldowns.get((test.skill or "").lower()),
            )
            for test in await self.catalog(AssessmentKind.SKILL)
        ]

    async def start_skill(
        self, principal: Principal, assessment_id: uuid.UUID
    ) -> AttemptResponse:
        """Начать тест на навык. Опроса нет: шкала одна для всех."""
        await self.expire_overdue(user_id=principal.id)
        assessment = await self.session.scalar(
            select(Assessment)
            .where(
                Assessment.id == assessment_id,
                Assessment.is_active,
                Assessment.owner_id.is_(None),
                Assessment.kind == AssessmentKind.SKILL,
            )
            .options(selectinload(Assessment.tasks))
        )
        if assessment is None or assessment.skill is None:
            raise NotFoundError("Тест не найден", code="assessment_not_found")
        if await self._active_attempt(principal.id) is not None:
            raise ConflictError(
                "Сначала завершите начатый тест", code="attempt_in_progress"
            )
        available_at = (await self._skill_cooldowns(principal.id)).get(
            assessment.skill.lower()
        )
        if available_at is not None:
            raise AppError(
                "Повторно пройти тест по этому навыку можно "
                f"с {available_at:%d.%m.%Y %H:%M} UTC",
                code="attempt_cooldown",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        snapshot = await self.candidates.snapshot(principal.id)
        if snapshot is None:
            raise ConflictError(
                "Сначала создайте профиль кандидата", code="profile_required"
            )
        attempt = self.new_attempt(
            principal,
            assessment,
            # Задачи — из всего банка: подбор по стеку исказил бы уровень.
            skills=set(),
            survey={},
            claimed_grade=snapshot.get("grade"),
        )
        self.session.add(attempt)
        await self.session.commit()
        return await self.view(await self._load(principal, attempt.id))

    def new_attempt(
        self,
        principal: Principal,
        assessment: Assessment,
        *,
        skills: set[str],
        survey: dict[str, Any],
        claimed_grade: str | None,
        assignment_id: uuid.UUID | None = None,
    ) -> Attempt:
        """Попытка с подобранными задачами и запущенным таймером теста."""
        active_tasks = [t for t in assessment.tasks if t.is_active]
        chosen = select_tasks(
            active_tasks, skills, assessment.tasks_per_attempt, random.Random()
        )
        now = clock.now()
        return Attempt(
            user_id=principal.id,
            assessment_id=assessment.id,
            assignment_id=assignment_id,
            specialization=assessment.specialization,
            target_grade=assessment.grade,
            skill=assessment.skill,
            claimed_grade=claimed_grade,
            survey=survey,
            status=AttemptStatus.IN_PROGRESS,
            started_at=now,
            deadline_at=now + timedelta(seconds=assessment.time_limit_seconds),
            max_score=sum(t.points for t in chosen),
            tasks=[
                AttemptTask(
                    task_id=task.id,
                    position=position,
                    max_points=task.points,
                    time_limit_seconds=task.time_limit_seconds,
                )
                for position, task in enumerate(chosen, start=1)
            ],
        )

    async def get(self, principal: Principal, attempt_id: uuid.UUID) -> AttemptResponse:
        attempt = await self._load(principal, attempt_id)
        await self._expire_if_overdue(attempt)
        return await self.view(attempt)

    async def current_task(
        self, principal: Principal, attempt_id: uuid.UUID
    ) -> TaskView:
        attempt = await self._load(principal, attempt_id, lock=True)
        await self._expire_if_overdue(attempt)
        self._ensure_in_progress(attempt)
        current = self._current(attempt)
        assert current is not None  # иначе попытка была бы завершена
        now = clock.now()
        if current.started_at is None:
            current.started_at = now
            await self.session.commit()
        task = current.task
        task_left = (
            current.time_limit_seconds - (now - current.started_at).total_seconds()
        )
        attempt_left = (attempt.deadline_at - now).total_seconds()
        return TaskView(
            attempt_task_id=current.id,
            position=current.position,
            total=len(attempt.tasks),
            kind=task.kind,
            prompt=task.prompt,
            code=task.code,
            options=[TaskOption(**option) for option in task.options],
            points=current.max_points,
            skills=task.skills,
            time_limit_seconds=current.time_limit_seconds,
            time_left_seconds=round(max(0.0, min(task_left, attempt_left)), 1),
            started_at=current.started_at,
        )

    async def answer(
        self, principal: Principal, attempt_id: uuid.UUID, data: AnswerRequest
    ) -> AnswerResponse:
        attempt = await self._load(principal, attempt_id, lock=True)
        await self._expire_if_overdue(attempt)
        self._ensure_in_progress(attempt)
        current = self._current(attempt)
        if current is None or current.id != data.attempt_task_id:
            raise ConflictError(
                "Отвечать можно только на текущую задачу", code="not_current_task"
            )
        if current.started_at is None:
            raise ConflictError("Сначала получите задачу", code="task_not_started")

        answer = validate_answer(current.task, data.answer)
        now = clock.now()
        spent = (now - current.started_at).total_seconds()
        timed_out = spent > current.time_limit_seconds + settings.time_grace_seconds
        fraction, is_correct = score(current.task, answer)

        current.answered_at = now
        current.time_spent_seconds = round(spent, 2)
        current.answer = answer
        current.skipped = answer is None
        current.timed_out = timed_out
        # Ответ после лимита задачи не засчитывается.
        current.is_correct = is_correct and not timed_out
        current.points_awarded = (
            0.0 if timed_out else round(fraction * current.max_points, 2)
        )

        finished = self._current(attempt) is None
        if finished:
            await self._finalize(attempt, AttemptStatus.COMPLETED)
        await self.session.commit()
        return AnswerResponse(
            time_spent_seconds=current.time_spent_seconds,
            timed_out=timed_out,
            finished=finished,
            attempt=await self.view(attempt),
        )

    async def finish(
        self, principal: Principal, attempt_id: uuid.UUID
    ) -> AttemptResponse:
        """Досрочное завершение: оставшиеся задачи — 0 баллов."""
        attempt = await self._load(principal, attempt_id, lock=True)
        await self._expire_if_overdue(attempt)
        if attempt.status == AttemptStatus.IN_PROGRESS:
            await self._finalize(attempt, AttemptStatus.COMPLETED)
            await self.session.commit()
        return await self.view(attempt)

    async def history(self, principal: Principal) -> list[AttemptSummary]:
        await self.expire_overdue(user_id=principal.id)
        attempts = await self.session.scalars(
            select(Attempt)
            .where(Attempt.user_id == principal.id)
            .options(selectinload(Attempt.assessment))
            .order_by(Attempt.started_at.desc())
        )
        return [
            AttemptSummary(
                id=a.id,
                title=a.assessment.title,
                kind=a.assessment.kind,
                specialization=a.specialization,
                target_grade=a.target_grade,
                skill=a.skill,
                industry=a.survey.get("industry"),
                status=a.status,
                started_at=a.started_at,
                finished_at=a.finished_at,
                duration_seconds=a.duration_seconds,
                percent=a.percent,
                outcome=a.outcome,
                confirmed_grade=a.confirmed_grade,
                level=level_of(a),
                assignment_id=a.assignment_id,
            )
            for a in attempts
        ]

    async def status(self, user_id: uuid.UUID) -> AssessmentStatus:
        await self.expire_overdue(user_id=user_id)
        best = await self._best_confirmation(user_id)
        active = await self._active_attempt(user_id)
        total = await self.session.scalar(
            select(func.count()).where(Attempt.user_id == user_id)
        )
        verified = None
        if best is not None:
            assert (
                best.finished_at and best.confirmed_grade and best.percent is not None
            )
            verified = VerifiedCategory(
                specialization=best.specialization,
                grade=best.confirmed_grade,
                verified_at=best.finished_at,
                valid_until=best.finished_at
                + timedelta(days=settings.confirmation_valid_days),
                attempt_id=best.id,
                percent=best.percent,
            )
        return AssessmentStatus(
            verified=verified,
            skills=await self._verified_skills(user_id),
            active_attempt_id=active.id if active else None,
            cooldowns=await self._cooldowns(user_id),
            attempts_total=total or 0,
        )

    async def expire_overdue(self, user_id: uuid.UUID | None = None) -> int:
        """Завершает попытки с истёкшим временем (фоново и при обращении)."""
        query = _attempt_query().where(
            Attempt.status == AttemptStatus.IN_PROGRESS,
            Attempt.deadline_at < clock.now() - _grace(),
        )
        if user_id is not None:
            query = query.where(Attempt.user_id == user_id)
        attempts = list(await self.session.scalars(query.with_for_update(of=Attempt)))
        for attempt in attempts:
            await self._finalize(attempt, AttemptStatus.EXPIRED)
        if attempts:
            await self.session.commit()
        return len(attempts)

    # --- Представление -----------------------------------------------------------

    async def view(self, attempt: Attempt) -> AttemptResponse:
        now = clock.now()
        result = None
        if attempt.status in FINISHED:
            result = await self._result(attempt)
        left = (
            max(0.0, (attempt.deadline_at - now).total_seconds())
            if attempt.status == AttemptStatus.IN_PROGRESS
            else 0.0
        )
        return AttemptResponse(
            id=attempt.id,
            assessment=AssessmentInfo.model_validate(attempt.assessment),
            status=attempt.status,
            survey=attempt.survey,
            claimed_grade=attempt.claimed_grade,
            started_at=attempt.started_at,
            deadline_at=attempt.deadline_at,
            finished_at=attempt.finished_at,
            time_left_seconds=round(left, 1),
            total_tasks=len(attempt.tasks),
            answered_tasks=sum(1 for t in attempt.tasks if t.answered_at),
            max_score=attempt.max_score,
            result=result,
        )

    async def _result(self, attempt: Attempt) -> AttemptResult:
        assert attempt.finished_at is not None
        per_skill: dict[str, list[float]] = defaultdict(lambda: [0.0, 0])
        tasks = []
        for item in attempt.tasks:
            for skill in item.task.skills:
                per_skill[skill][0] += item.points_awarded
                per_skill[skill][1] += item.max_points
            # Правильные ответы не раскрываются: банк задач используется
            # в повторных попытках.
            tasks.append(
                TaskResult(
                    position=item.position,
                    prompt=item.task.prompt,
                    kind=item.task.kind,
                    skills=item.task.skills,
                    max_points=item.max_points,
                    points_awarded=item.points_awarded,
                    is_correct=item.is_correct,
                    time_limit_seconds=item.time_limit_seconds,
                    time_spent_seconds=item.time_spent_seconds,
                    timed_out=item.timed_out,
                    skipped=item.skipped,
                )
            )
        available_at = None
        if attempt.outcome == Outcome.NOT_CONFIRMED:
            available_at = attempt.finished_at + timedelta(
                hours=settings.attempt_cooldown_hours
            )
        return AttemptResult(
            score=attempt.score or 0,
            max_score=attempt.max_score,
            percent=attempt.percent or 0,
            outcome=attempt.outcome,
            target_grade=attempt.target_grade,
            confirmed_grade=attempt.confirmed_grade,
            skill=attempt.skill,
            level=level_of(attempt),
            message=(
                "Результат отправлен работодателю."
                if attempt.assignment_id
                else result_message(attempt, available_at)
            ),
            duration_seconds=attempt.duration_seconds or 0,
            tasks=tasks,
            skills=[
                SkillScore(
                    skill=skill,
                    points=round(points, 2),
                    max_points=int(maximum),
                    percent=round(points * 100 / maximum, 1) if maximum else 0,
                )
                for skill, (points, maximum) in sorted(per_skill.items())
            ],
        )

    # --- Внутреннее ---------------------------------------------------------------

    async def _load(
        self, principal: Principal, attempt_id: uuid.UUID, *, lock: bool = False
    ) -> Attempt:
        query = _attempt_query().where(Attempt.id == attempt_id)
        if lock:
            # Ответы и завершение одной попытки выполняются по очереди:
            # параллельный запрос не засчитает задачу дважды.
            query = query.with_for_update(of=Attempt)
        attempt = await self.session.scalar(query)
        # Чужие попытки неотличимы от несуществующих.
        if attempt is None or attempt.user_id != principal.id:
            raise NotFoundError("Попытка не найдена", code="attempt_not_found")
        return attempt

    async def active_attempt(self, user_id: uuid.UUID) -> Attempt | None:
        return await self._active_attempt(user_id)

    async def _active_attempt(self, user_id: uuid.UUID) -> Attempt | None:
        return await self.session.scalar(
            select(Attempt).where(
                Attempt.user_id == user_id,
                Attempt.status == AttemptStatus.IN_PROGRESS,
            )
        )

    async def _cooldowns(self, user_id: uuid.UUID) -> list[CooldownInfo]:
        """Специализации, по которым повторная попытка пока недоступна."""
        rows = await self.session.execute(
            select(Attempt.specialization, func.max(Attempt.finished_at))
            .where(
                Attempt.user_id == user_id,
                Attempt.finished_at.is_not(None),
                Attempt.assignment_id.is_(None),
                Attempt.skill.is_(None),
            )
            .group_by(Attempt.specialization)
        )
        now = clock.now()
        cooldown = timedelta(hours=settings.attempt_cooldown_hours)
        return [
            CooldownInfo(specialization=spec, available_at=finished + cooldown)
            for spec, finished in rows
            if finished + cooldown > now
        ]

    async def _skill_cooldowns(self, user_id: uuid.UUID) -> dict[str, datetime]:
        """Навыки (в нижнем регистре), по которым повтор пока недоступен."""
        rows = await self.session.execute(
            select(func.lower(Attempt.skill), func.max(Attempt.finished_at))
            .where(
                Attempt.user_id == user_id,
                Attempt.finished_at.is_not(None),
                Attempt.skill.is_not(None),
            )
            .group_by(func.lower(Attempt.skill))
        )
        now = clock.now()
        cooldown = timedelta(hours=settings.attempt_cooldown_hours)
        return {
            skill: finished + cooldown
            for skill, finished in rows
            if finished + cooldown > now
        }

    async def _best_skill_attempts(self, user_id: uuid.UUID) -> list[Attempt]:
        """Лучший действующий результат по каждому навыку.

        Как и с грейдом, неудачная попытка не отменяет подтверждённый уровень.
        """
        since = clock.now() - timedelta(days=settings.confirmation_valid_days)
        attempts = await self.session.scalars(
            select(Attempt)
            .where(
                Attempt.user_id == user_id,
                Attempt.confirmed_level.is_not(None),
                Attempt.finished_at >= since,
            )
            .options(selectinload(Attempt.assessment))
        )
        best: dict[str, Attempt] = {}
        for attempt in attempts:
            key = (attempt.skill or "").lower()
            current = best.get(key)
            if current is None or (_level_rank(attempt), attempt.finished_at) > (
                _level_rank(current),
                current.finished_at,
            ):
                best[key] = attempt
        return sorted(best.values(), key=lambda a: (a.skill or "").lower())

    async def _verified_skills(self, user_id: uuid.UUID) -> list[VerifiedSkill]:
        return [
            self._verified_skill(attempt)
            for attempt in await self._best_skill_attempts(user_id)
            if level_of(attempt) is not None
        ]

    @staticmethod
    def _verified_skill(attempt: Attempt) -> VerifiedSkill:
        level = level_of(attempt)
        assert level and attempt.skill and attempt.finished_at
        return VerifiedSkill(
            skill=attempt.skill,
            level=level,
            verified_at=attempt.finished_at,
            valid_until=attempt.finished_at
            + timedelta(days=settings.confirmation_valid_days),
            attempt_id=attempt.id,
            percent=attempt.percent or 0,
            test_title=attempt.assessment.title,
        )

    async def _best_confirmation(self, user_id: uuid.UUID) -> Attempt | None:
        """Лучший действующий подтверждённый результат по всем специализациям.

        Неудачная попытка на грейд выше не отменяет уже подтверждённый.
        """
        since = clock.now() - timedelta(days=settings.confirmation_valid_days)
        attempts = await self.session.scalars(
            select(Attempt)
            .where(
                Attempt.user_id == user_id,
                Attempt.confirmed_grade.is_not(None),
                Attempt.finished_at >= since,
            )
            .options(selectinload(Attempt.assessment))
        )
        return max(
            attempts,
            key=lambda a: (GRADE_ORDER[Grade(a.confirmed_grade)], a.finished_at),
            default=None,
        )

    @staticmethod
    def _current(attempt: Attempt) -> AttemptTask | None:
        return next((t for t in attempt.tasks if t.answered_at is None), None)

    @staticmethod
    def _ensure_in_progress(attempt: Attempt) -> None:
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise ConflictError("Тест уже завершён", code="attempt_finished")

    async def _expire_if_overdue(self, attempt: Attempt) -> None:
        if (
            attempt.status == AttemptStatus.IN_PROGRESS
            and clock.now() > attempt.deadline_at + _grace()
        ):
            await self._finalize(attempt, AttemptStatus.EXPIRED)
            await self.session.commit()

    async def _finalize(self, attempt: Attempt, final_status: AttemptStatus) -> None:
        now = clock.now()
        for item in attempt.tasks:
            if item.answered_at is None:
                item.skipped = True
                item.points_awarded = 0.0
        finished_at = (
            min(now, attempt.deadline_at)
            if final_status == AttemptStatus.EXPIRED
            else now
        )
        total = sum(item.points_awarded for item in attempt.tasks)
        percent = (
            round(total * 100 / attempt.max_score, 1) if attempt.max_score else 0.0
        )
        # Тесты работодателей грейд не подтверждают.
        outcome: Outcome | None = None
        confirmed: Grade | None = None
        level: dict[str, Any] | None = None
        if attempt.skill is not None:
            outcome, level = evaluate_level(percent, attempt.assessment.levels)
        elif not attempt.assignment_id:
            outcome, confirmed = evaluate(percent, Grade(attempt.target_grade))

        attempt.status = final_status
        attempt.finished_at = finished_at
        attempt.duration_seconds = round(
            (finished_at - attempt.started_at).total_seconds(), 1
        )
        attempt.score = round(total, 2)
        attempt.percent = percent
        attempt.outcome = outcome
        attempt.confirmed_grade = confirmed
        attempt.confirmed_level = level["id"] if level else None
        await self.session.flush()
        logger.info("Attempt %s finished: %s%% -> %s", attempt.id, percent, outcome)
        if attempt.assignment_id:
            await publish_assignment_result(self.session, attempt)
        elif attempt.skill is not None:
            await self._publish_skill(attempt)
        else:
            await self._publish(attempt)

    async def _publish(self, attempt: Attempt) -> None:
        """Категория — в профиль кандидата, результат — в уведомления.

        Доставка через outbox: недоступность соседних сервисов не теряет
        результат и не ломает ответ кандидату.
        """
        best = await self._best_confirmation(attempt.user_id)
        industry = attempt.survey.get("industry")
        enqueue(
            self.session,
            OutboxMessage,
            CANDIDATE_ASSESSMENT,
            {
                "user_id": str(attempt.user_id),
                "industry": industry,
                "specialization": best.specialization
                if best
                else attempt.specialization,
                "verified_grade": best.confirmed_grade if best else None,
                "verified_at": best.finished_at.isoformat() if best else None,
                "attempt_id": str(best.id) if best else None,
                "test_title": best.assessment.title if best else None,
                "percent": best.percent if best else None,
            },
        )
        titles = {
            Outcome.EXCEEDED: "Тест пройден на уровень выше заявленного",
            Outcome.CONFIRMED: "Грейд подтверждён",
            Outcome.NOT_CONFIRMED: "Грейд пока не подтверждён",
        }
        available_at = (
            attempt.finished_at + timedelta(hours=settings.attempt_cooldown_hours)
            if attempt.outcome == Outcome.NOT_CONFIRMED and attempt.finished_at
            else None
        )
        industry_title = INDUSTRY_TITLES.get(Industry(industry)) if industry else None
        body = (
            f"Тест «{attempt.assessment.title}»"
            + (f" ({industry_title})" if industry_title else "")
            + f": {attempt.score:g} из {attempt.max_score} баллов.\n"
            + result_message(attempt, available_at)
        )
        enqueue(
            self.session,
            OutboxMessage,
            NOTIFICATION,
            {
                "user_id": str(attempt.user_id),
                "type": "assessment.completed",
                "title": titles[Outcome(attempt.outcome)],
                "body": body,
                "link": f"/assessments/attempts/{attempt.id}",
                "data": {
                    "attempt_id": str(attempt.id),
                    "outcome": attempt.outcome,
                    "percent": attempt.percent,
                },
                "email": True,
                "dedup_key": f"assessment:{attempt.id}:finished",
            },
        )

    async def _publish_skill(self, attempt: Attempt) -> None:
        """Лучший действующий уровень навыка — в профиль, итог — в уведомления."""
        assert attempt.skill is not None
        best = next(
            (
                a
                for a in await self._best_skill_attempts(attempt.user_id)
                if (a.skill or "").lower() == attempt.skill.lower()
            ),
            None,
        )
        verified = self._verified_skill(best) if best and level_of(best) else None
        enqueue(
            self.session,
            OutboxMessage,
            CANDIDATE_SKILL,
            {
                "user_id": str(attempt.user_id),
                "skill": attempt.skill,
                # None — подтверждённого уровня нет (убрать отметку).
                "verification": verified.model_dump(mode="json") if verified else None,
            },
        )
        available_at = (
            attempt.finished_at + timedelta(hours=settings.attempt_cooldown_hours)
            if attempt.outcome == Outcome.NOT_CONFIRMED and attempt.finished_at
            else None
        )
        level = level_of(attempt)
        enqueue(
            self.session,
            OutboxMessage,
            NOTIFICATION,
            {
                "user_id": str(attempt.user_id),
                "type": "assessment.completed",
                "title": f"{attempt.skill}: уровень {level.title} подтверждён"
                if level
                else f"{attempt.skill}: уровень пока не подтверждён",
                "body": f"Тест «{attempt.assessment.title}»: {attempt.score:g} "
                f"из {attempt.max_score} баллов.\n"
                + skill_result_message(attempt, available_at),
                "link": f"/assessments/attempts/{attempt.id}",
                "data": {
                    "attempt_id": str(attempt.id),
                    "skill": attempt.skill,
                    "level": level.id if level else None,
                    "percent": attempt.percent,
                },
                "email": True,
                "dedup_key": f"assessment:{attempt.id}:finished",
            },
        )
