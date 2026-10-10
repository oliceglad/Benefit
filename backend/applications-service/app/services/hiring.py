"""Процесс найма: от отклика или принятого приглашения до оффера.

Процесс создаётся автоматически, когда кандидат откликается на вакансию
или принимает приглашение. Работодатель ведёт кандидата по этапам,
назначает ответственного, интервью и оффер; кандидат отвечает на оффер или
выходит из процесса. Каждое действие пишется в историю, а значимые для
кандидата события дублируются в уведомления и переписку.

Работодатель видит только свои процессы, кандидат — только свои; чужие
неотличимы от несуществующих (404).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from benefit_common.errors import AppError, ConflictError, NotFoundError
from benefit_common.outbox import enqueue
from benefit_common.security import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    STAGE_ORDER,
    Application,
    ApplicationStatus,
    HiringEvent,
    HiringProcess,
    HiringSource,
    HiringStage,
    HiringStatus,
    Interview,
    InterviewStatus,
    JobOffer,
    OfferStatus,
    OutboxMessage,
    TeamMember,
)
from app.schemas.hiring import (
    CandidateReply,
    CommentCreate,
    InterviewCancel,
    InterviewCreate,
    InterviewResult,
    InterviewUpdate,
    OfferCreate,
    RejectRequest,
    ResponsibleUpdate,
    StageChange,
    TeamMemberIn,
    TeamMemberUpdate,
)
from app.services.delivery import CHAT_SYNC, NOTIFICATION

STAGE_TITLES = {
    HiringStage.NEW: "Новый",
    HiringStage.SCREENING: "Отбор",
    HiringStage.INTERVIEW: "Интервью",
    HiringStage.ASSESSMENT: "Тестовое задание",
    HiringStage.OFFER: "Оффер",
    HiringStage.HIRED: "Нанят",
}
STATUS_TITLES = {
    HiringStatus.ACTIVE: "В процессе",
    HiringStatus.HIRED: "Нанят",
    HiringStatus.REJECTED: "Отказ",
    HiringStatus.WITHDRAWN: "Кандидат вышел из процесса",
}
INTERVIEW_KIND_TITLES = {
    "hr": "Интервью с HR",
    "technical": "Техническое интервью",
    "final": "Финальное интервью",
    "other": "Встреча",
}
INTERVIEW_FORMAT_TITLES = {
    "online": "Онлайн",
    "office": "В офисе",
    "phone": "По телефону",
}
INTERVIEW_STATUS_TITLES = {
    InterviewStatus.SCHEDULED: "Назначено",
    InterviewStatus.COMPLETED: "Проведено",
    InterviewStatus.CANCELLED: "Отменено",
    InterviewStatus.NO_SHOW: "Кандидат не пришёл",
}
OFFER_STATUS_TITLES = {
    OfferStatus.SENT: "Ожидает ответа",
    OfferStatus.ACCEPTED: "Принят",
    OfferStatus.DECLINED: "Отклонён",
    OfferStatus.WITHDRAWN: "Отозван",
    OfferStatus.EXPIRED: "Истёк срок ответа",
}
# Типы записей истории. Видимые кандидату отмечены в _event (visible=True).
EVENT_TITLES = {
    "created": "Процесс найма начат",
    "stage_changed": "Смена этапа",
    "responsible_changed": "Назначен ответственный",
    "comment": "Заметка",
    "interview_scheduled": "Назначено интервью",
    "interview_updated": "Интервью перенесено или изменено",
    "interview_cancelled": "Интервью отменено",
    "interview_completed": "Интервью проведено",
    "interview_no_show": "Кандидат не пришёл на интервью",
    "offer_sent": "Отправлен оффер",
    "offer_withdrawn": "Оффер отозван",
    "offer_accepted": "Оффер принят",
    "offer_declined": "Оффер отклонён",
    "offer_expired": "Истёк срок ответа на оффер",
    "hired": "Кандидат нанят",
    "rejected": "Отказ",
    "withdrawn": "Кандидат вышел из процесса",
}

EMPLOYER = "employer"
CANDIDATE = "candidate"
SYSTEM = "system"


def now() -> datetime:
    return datetime.now(UTC)


def not_found() -> NotFoundError:
    return NotFoundError("Процесс найма не найден", code="hiring_process_not_found")


def _ensure_active(process: HiringProcess) -> None:
    if process.status != HiringStatus.ACTIVE:
        raise ConflictError(
            "Процесс найма уже завершён", code=f"hiring_{process.status}"
        )


def _when(value: datetime) -> str:
    return f"{value.astimezone(UTC):%d.%m.%Y %H:%M} UTC"


def active_offer(process: HiringProcess) -> JobOffer | None:
    return next((o for o in process.offers if o.status == OfferStatus.SENT), None)


def next_interview(process: HiringProcess) -> Interview | None:
    scheduled = [i for i in process.interviews if i.status == InterviewStatus.SCHEDULED]
    return min(scheduled, key=lambda i: i.scheduled_at, default=None)


class HiringService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        # Статус отклика или приглашения, с которого начался процесс: он
        # передаётся в переписку вместе с событиями.
        self._source_status: dict[uuid.UUID, str] = {}

    # --- Создание и синхронизация с откликами и приглашениями ------------------------
    # Вызываются внутри транзакции другого сервиса; коммит — у вызывающего.

    async def open(
        self,
        *,
        source: HiringSource,
        source_id: uuid.UUID,
        employer_id: uuid.UUID,
        candidate_id: uuid.UUID,
        vacancy_id: str | None,
        vacancy_title: str,
        company_name: str,
        company_id: uuid.UUID | None,
        actor_id: uuid.UUID,
    ) -> HiringProcess:
        existing = await self._by_source(source, source_id)
        if existing is not None:
            return existing
        process = HiringProcess(
            employer_id=employer_id,
            candidate_id=candidate_id,
            source=source,
            source_id=source_id,
            vacancy_id=vacancy_id,
            vacancy_title=vacancy_title,
            company_name=company_name,
            company_id=company_id,
            stage=HiringStage.NEW,
            status=HiringStatus.ACTIVE,
            stage_changed_at=now(),
            interviews=[],
            offers=[],
            events=[],
        )
        self.session.add(process)
        await self.session.flush()
        self._source_status[process.id] = (
            ApplicationStatus.NEW if source == HiringSource.APPLICATION else "accepted"
        )
        self._event(
            process,
            "created",
            actor_id,
            CANDIDATE,
            data={"source": source.value},
            visible=True,
        )
        return process

    async def on_application_status(
        self, application: Application, actor: Principal
    ) -> None:
        """Смена статуса отклика отражается в процессе найма.

        Уведомления и сообщение в переписку уже отправил сервис откликов,
        поэтому здесь — только этап и история.
        """
        process = await self._by_source(HiringSource.APPLICATION, application.id)
        if process is None or process.status != HiringStatus.ACTIVE:
            return
        if application.status == ApplicationStatus.INVITED:
            self._advance(process, HiringStage.INTERVIEW, actor.id, EMPLOYER)
        elif application.status == ApplicationStatus.REJECTED:
            self._finish(
                process,
                HiringStatus.REJECTED,
                actor.id,
                EMPLOYER,
                comment=application.employer_message,
                quiet=True,
            )
        elif application.status == ApplicationStatus.WITHDRAWN:
            self._finish(
                process, HiringStatus.WITHDRAWN, actor.id, CANDIDATE, quiet=True
            )

    # --- Команда ----------------------------------------------------------------------

    async def team(
        self, employer: Principal, include_inactive: bool = False
    ) -> list[TeamMember]:
        query = select(TeamMember).where(TeamMember.employer_id == employer.id)
        if not include_inactive:
            query = query.where(TeamMember.is_active.is_(True))
        return list(await self.session.scalars(query.order_by(TeamMember.full_name)))

    async def add_member(self, employer: Principal, data: TeamMemberIn) -> TeamMember:
        member = TeamMember(employer_id=employer.id, **data.model_dump())
        self.session.add(member)
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def update_member(
        self, employer: Principal, member_id: uuid.UUID, data: TeamMemberUpdate
    ) -> TeamMember:
        member = await self.session.get(TeamMember, member_id)
        if member is None or member.employer_id != employer.id:
            raise NotFoundError("Сотрудник не найден", code="team_member_not_found")
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "is_active" and value is None:
                continue
            setattr(member, field, value)
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def members(
        self, employer_id: uuid.UUID, ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, TeamMember]:
        if not ids:
            return {}
        rows = await self.session.scalars(
            select(TeamMember).where(
                TeamMember.id.in_(ids), TeamMember.employer_id == employer_id
            )
        )
        return {m.id: m for m in rows}

    async def _active_members(
        self, employer: Principal, ids: list[uuid.UUID]
    ) -> list[uuid.UUID]:
        unique = list(dict.fromkeys(ids))
        found = await self.members(employer.id, set(unique))
        if len(found) != len(unique) or not all(m.is_active for m in found.values()):
            raise AppError(
                "Сотрудник не найден в команде компании",
                code="team_member_not_found",
                status_code=422,
            )
        return unique

    # --- Работодатель: список и карточка ----------------------------------------------

    async def employer_list(
        self,
        employer: Principal,
        *,
        status: HiringStatus | None = None,
        stage: HiringStage | None = None,
        vacancy_id: str | None = None,
        responsible_id: uuid.UUID | None = None,
        candidate_id: uuid.UUID | None = None,
    ) -> list[HiringProcess]:
        query = select(HiringProcess).where(HiringProcess.employer_id == employer.id)
        if status is not None:
            query = query.where(HiringProcess.status == status)
        if stage is not None:
            query = query.where(HiringProcess.stage == stage)
        if vacancy_id is not None:
            query = query.where(HiringProcess.vacancy_id == vacancy_id)
        if responsible_id is not None:
            query = query.where(HiringProcess.responsible_id == responsible_id)
        if candidate_id is not None:
            query = query.where(HiringProcess.candidate_id == candidate_id)
        processes = list(
            await self.session.scalars(query.order_by(HiringProcess.updated_at.desc()))
        )
        await self._expire_offers(processes)
        return processes

    async def candidate_list(self, candidate: Principal) -> list[HiringProcess]:
        processes = list(
            await self.session.scalars(
                select(HiringProcess)
                .where(HiringProcess.candidate_id == candidate.id)
                .order_by(HiringProcess.updated_at.desc())
            )
        )
        await self._expire_offers(processes)
        return processes

    async def get(
        self, principal: Principal, process_id: uuid.UUID, *, lock: bool = False
    ) -> HiringProcess:
        query = select(HiringProcess).where(HiringProcess.id == process_id)
        if lock:
            # Изменения одного процесса — по очереди (например, двойное
            # принятие оффера или оффер одновременно с отказом).
            query = query.with_for_update(of=HiringProcess)
        process = await self.session.scalar(
            query.execution_options(populate_existing=True)
        )
        if process is None or principal.id not in (
            process.employer_id,
            process.candidate_id,
        ):
            raise not_found()
        await self._expire_offers([process])
        if process.source == HiringSource.APPLICATION:
            application = await self.session.get(Application, process.source_id)
            if application is not None:
                self._source_status[process.id] = application.status
        return process

    async def _employer_process(
        self, employer: Principal, process_id: uuid.UUID
    ) -> HiringProcess:
        process = await self.get(employer, process_id, lock=True)
        if process.employer_id != employer.id:
            raise not_found()
        return process

    async def _candidate_process(
        self, candidate: Principal, process_id: uuid.UUID
    ) -> HiringProcess:
        process = await self.get(candidate, process_id, lock=True)
        if process.candidate_id != candidate.id:
            raise not_found()
        return process

    # --- Работодатель: этапы, ответственный, заметки, отказ ---------------------------

    async def change_stage(
        self, employer: Principal, process_id: uuid.UUID, data: StageChange
    ) -> HiringProcess:
        process = await self._employer_process(employer, process_id)
        _ensure_active(process)
        if process.stage == data.stage:
            raise ConflictError("Кандидат уже на этом этапе", code="hiring_same_stage")
        self._set_stage(process, HiringStage(data.stage), employer.id, data.comment)
        return await self._save(process)

    async def set_responsible(
        self, employer: Principal, process_id: uuid.UUID, data: ResponsibleUpdate
    ) -> HiringProcess:
        process = await self._employer_process(employer, process_id)
        name = None
        if data.responsible_id is not None:
            await self._active_members(employer, [data.responsible_id])
            member = await self.session.get(TeamMember, data.responsible_id)
            assert member is not None
            name = member.full_name
        if process.responsible_id == data.responsible_id:
            return process
        process.responsible_id = data.responsible_id
        self._event(
            process,
            "responsible_changed",
            employer.id,
            EMPLOYER,
            data={
                "responsible_id": str(data.responsible_id)
                if data.responsible_id
                else None,
                "full_name": name,
            },
        )
        return await self._save(process)

    async def comment(
        self, employer: Principal, process_id: uuid.UUID, data: CommentCreate
    ) -> HiringProcess:
        """Внутренняя заметка: кандидат её не видит."""
        process = await self._employer_process(employer, process_id)
        self._event(process, "comment", employer.id, EMPLOYER, comment=data.text)
        return await self._save(process)

    async def reject(
        self, employer: Principal, process_id: uuid.UUID, data: RejectRequest
    ) -> HiringProcess:
        process = await self._employer_process(employer, process_id)
        _ensure_active(process)
        process.rejection_reason = data.reason
        self._finish(
            process,
            HiringStatus.REJECTED,
            employer.id,
            EMPLOYER,
            comment=data.message,
            internal_reason=data.reason,
        )
        await self._sync_application(process, ApplicationStatus.REJECTED, data.message)
        return await self._save(process)

    # --- Работодатель: интервью -------------------------------------------------------

    async def schedule_interview(
        self, employer: Principal, process_id: uuid.UUID, data: InterviewCreate
    ) -> HiringProcess:
        process = await self._employer_process(employer, process_id)
        _ensure_active(process)
        interviewers = await self._active_members(employer, data.interviewer_ids)
        interview = Interview(
            **data.model_dump(exclude={"interviewer_ids"}),
            interviewer_ids=interviewers,
            status=InterviewStatus.SCHEDULED,
        )
        process.interviews.append(interview)
        await self.session.flush()
        self._advance(process, HiringStage.INTERVIEW, employer.id, EMPLOYER)
        text = (
            f"{INTERVIEW_KIND_TITLES[interview.kind]} — {_when(interview.scheduled_at)}"
            f", {INTERVIEW_FORMAT_TITLES[interview.format].lower()}"
            + (f" ({interview.location})" if interview.location else "")
            + "."
        )
        if interview.note_for_candidate:
            text += f"\n\n{interview.note_for_candidate}"
        event = self._event(
            process,
            "interview_scheduled",
            employer.id,
            EMPLOYER,
            data=self._interview_data(interview),
            visible=True,
        )
        self._tell_candidate(
            process, event, f"Интервью: «{process.vacancy_title}»", text
        )
        return await self._save(process)

    async def update_interview(
        self,
        employer: Principal,
        process_id: uuid.UUID,
        interview_id: uuid.UUID,
        data: InterviewUpdate,
    ) -> HiringProcess:
        process = await self._employer_process(employer, process_id)
        _ensure_active(process)
        interview = self._interview(process, interview_id)
        if interview.status != InterviewStatus.SCHEDULED:
            raise ConflictError(
                "Изменить можно только назначенное интервью",
                code=f"interview_{interview.status}",
            )
        changes = data.model_dump(exclude_unset=True)
        if changes.get("interviewer_ids") is not None:
            changes["interviewer_ids"] = await self._active_members(
                employer, changes["interviewer_ids"]
            )
        for field, value in changes.items():
            if value is None and field in {
                "kind",
                "scheduled_at",
                "duration_minutes",
                "format",
                "interviewer_ids",
            }:
                continue
            setattr(interview, field, value)
        event = self._event(
            process,
            "interview_updated",
            employer.id,
            EMPLOYER,
            data=self._interview_data(interview),
            visible=True,
        )
        self._tell_candidate(
            process,
            event,
            f"Интервью изменено: «{process.vacancy_title}»",
            f"Новое время: {_when(interview.scheduled_at)}, "
            f"{INTERVIEW_FORMAT_TITLES[interview.format].lower()}"
            + (f" ({interview.location})" if interview.location else "")
            + ".",
        )
        return await self._save(process)

    async def cancel_interview(
        self,
        employer: Principal,
        process_id: uuid.UUID,
        interview_id: uuid.UUID,
        data: InterviewCancel,
    ) -> HiringProcess:
        process = await self._employer_process(employer, process_id)
        interview = self._interview(process, interview_id)
        if interview.status != InterviewStatus.SCHEDULED:
            raise ConflictError(
                "Интервью уже проведено или отменено",
                code=f"interview_{interview.status}",
            )
        interview.status = InterviewStatus.CANCELLED
        event = self._event(
            process,
            "interview_cancelled",
            employer.id,
            EMPLOYER,
            data=self._interview_data(interview),
            comment=data.message,
            visible=True,
        )
        self._tell_candidate(
            process,
            event,
            f"Интервью отменено: «{process.vacancy_title}»",
            f"Интервью {_when(interview.scheduled_at)} отменено."
            + (f"\n\n{data.message}" if data.message else ""),
        )
        return await self._save(process)

    async def record_result(
        self,
        employer: Principal,
        process_id: uuid.UUID,
        interview_id: uuid.UUID,
        data: InterviewResult,
    ) -> HiringProcess:
        """Итог интервью: оценка и отзыв видны только работодателю."""
        process = await self._employer_process(employer, process_id)
        interview = self._interview(process, interview_id)
        if interview.status not in (
            InterviewStatus.SCHEDULED,
            InterviewStatus.COMPLETED,
            InterviewStatus.NO_SHOW,
        ):
            raise ConflictError(
                "Интервью отменено", code=f"interview_{interview.status}"
            )
        if interview.scheduled_at > now():
            raise ConflictError(
                "Итоги можно внести после начала интервью",
                code="interview_not_started",
            )
        interview.status = InterviewStatus(data.status)
        interview.rating = data.rating
        interview.feedback = data.feedback
        interview.completed_at = now()
        self._event(
            process,
            f"interview_{data.status}",
            employer.id,
            EMPLOYER,
            data={"interview_id": str(interview.id), "rating": data.rating},
            comment=data.feedback,
        )
        return await self._save(process)

    # --- Работодатель: оффер ----------------------------------------------------------

    async def make_offer(
        self, employer: Principal, process_id: uuid.UUID, data: OfferCreate
    ) -> HiringProcess:
        process = await self._employer_process(employer, process_id)
        _ensure_active(process)
        if active_offer(process) is not None:
            raise ConflictError(
                "У кандидата уже есть оффер, ожидающий ответа: отзовите его, "
                "чтобы отправить новый",
                code="offer_pending",
            )
        values = data.model_dump(exclude={"expires_in_days"})
        values["position_title"] = values["position_title"] or process.vacancy_title
        offer = JobOffer(
            **values,
            status=OfferStatus.SENT,
            expires_at=now() + timedelta(days=data.expires_in_days),
        )
        process.offers.append(offer)
        await self.session.flush()
        self._advance(process, HiringStage.OFFER, employer.id, EMPLOYER)
        event = self._event(
            process,
            "offer_sent",
            employer.id,
            EMPLOYER,
            data=self._offer_data(offer),
            visible=True,
        )
        salary = f"{offer.salary:,}".replace(",", " ")
        text = (
            f"{process.company_name} делает вам предложение о работе: "
            f"«{offer.position_title}», {salary} {offer.currency} "
            f"({'до вычета налогов' if offer.salary_type == 'gross' else 'на руки'})."
        )
        if offer.start_date:
            text += f"\nДата выхода: {offer.start_date:%d.%m.%Y}."
        if offer.message:
            text += f"\n\n{offer.message}"
        text += f"\n\nОтветьте до {offer.expires_at:%d.%m.%Y}."
        self._tell_candidate(process, event, f"Оффер: «{process.vacancy_title}»", text)
        return await self._save(process)

    async def withdraw_offer(
        self, employer: Principal, process_id: uuid.UUID, offer_id: uuid.UUID
    ) -> HiringProcess:
        process = await self._employer_process(employer, process_id)
        offer = self._offer(process, offer_id)
        self._ensure_offer_pending(offer)
        offer.status = OfferStatus.WITHDRAWN
        offer.responded_at = now()
        event = self._event(
            process,
            "offer_withdrawn",
            employer.id,
            EMPLOYER,
            data={"offer_id": str(offer.id)},
            visible=True,
        )
        self._tell_candidate(
            process,
            event,
            f"Оффер отозван: «{process.vacancy_title}»",
            f"{process.company_name} отозвал предложение о работе.",
            email=False,
        )
        return await self._save(process)

    # --- Кандидат ---------------------------------------------------------------------

    async def accept_offer(
        self,
        candidate: Principal,
        process_id: uuid.UUID,
        offer_id: uuid.UUID,
        data: CandidateReply,
    ) -> HiringProcess:
        process = await self._candidate_process(candidate, process_id)
        offer = self._offer(process, offer_id)
        self._ensure_offer_pending(offer)
        _ensure_active(process)
        offer.status = OfferStatus.ACCEPTED
        offer.candidate_message = data.message
        offer.responded_at = now()
        self._event(
            process,
            "offer_accepted",
            candidate.id,
            CANDIDATE,
            data={"offer_id": str(offer.id)},
            comment=data.message,
            visible=True,
        )
        # Принятый оффер завершает процесс: кандидат нанят.
        self._set_stage(process, HiringStage.HIRED, candidate.id, None, CANDIDATE)
        event = self._finish(process, HiringStatus.HIRED, candidate.id, CANDIDATE)
        self._tell_employer(
            process,
            event,
            f"Оффер принят: «{process.vacancy_title}»",
            "Кандидат принял ваше предложение о работе."
            + (f"\n\nКомментарий кандидата:\n{data.message}" if data.message else ""),
        )
        return await self._save(process)

    async def decline_offer(
        self,
        candidate: Principal,
        process_id: uuid.UUID,
        offer_id: uuid.UUID,
        data: CandidateReply,
    ) -> HiringProcess:
        process = await self._candidate_process(candidate, process_id)
        offer = self._offer(process, offer_id)
        self._ensure_offer_pending(offer)
        offer.status = OfferStatus.DECLINED
        offer.candidate_message = data.message
        offer.responded_at = now()
        event = self._event(
            process,
            "offer_declined",
            candidate.id,
            CANDIDATE,
            data={"offer_id": str(offer.id)},
            comment=data.message,
            visible=True,
        )
        self._tell_employer(
            process,
            event,
            f"Оффер отклонён: «{process.vacancy_title}»",
            "Кандидат отклонил предложение о работе."
            + (f"\n\nКомментарий кандидата:\n{data.message}" if data.message else ""),
        )
        return await self._save(process)

    async def candidate_withdraw(
        self, candidate: Principal, process_id: uuid.UUID, data: CandidateReply
    ) -> HiringProcess:
        process = await self._candidate_process(candidate, process_id)
        _ensure_active(process)
        event = self._finish(
            process,
            HiringStatus.WITHDRAWN,
            candidate.id,
            CANDIDATE,
            comment=data.message,
        )
        await self._sync_application(process, ApplicationStatus.WITHDRAWN, None)
        self._tell_employer(
            process,
            event,
            f"Кандидат вышел из процесса: «{process.vacancy_title}»",
            "Кандидат больше не рассматривает вакансию."
            + (f"\n\nКомментарий кандидата:\n{data.message}" if data.message else ""),
        )
        return await self._save(process)

    # --- Внутреннее -------------------------------------------------------------------

    async def _by_source(
        self, source: HiringSource, source_id: uuid.UUID
    ) -> HiringProcess | None:
        return await self.session.scalar(
            select(HiringProcess).where(
                HiringProcess.source == source, HiringProcess.source_id == source_id
            )
        )

    async def _save(self, process: HiringProcess) -> HiringProcess:
        process.updated_at = now()
        await self.session.commit()
        reloaded = await self.session.scalar(
            select(HiringProcess)
            .where(HiringProcess.id == process.id)
            .execution_options(populate_existing=True)
        )
        assert reloaded is not None
        return reloaded

    async def _expire_offers(self, processes: list[HiringProcess]) -> None:
        current = now()
        changed = False
        for process in processes:
            offer = active_offer(process)
            if offer is not None and offer.expires_at <= current:
                offer.status = OfferStatus.EXPIRED
                self._event(
                    process,
                    "offer_expired",
                    None,
                    SYSTEM,
                    data={"offer_id": str(offer.id)},
                    visible=True,
                )
                changed = True
        if changed:
            await self.session.commit()

    async def _sync_application(
        self,
        process: HiringProcess,
        status: ApplicationStatus,
        message: str | None,
    ) -> None:
        """Отказ или выход из процесса закрывает и отклик, с которого он начался."""
        if process.source != HiringSource.APPLICATION:
            return
        application = await self.session.get(Application, process.source_id)
        if application is None or application.status not in (
            ApplicationStatus.NEW,
            ApplicationStatus.VIEWED,
            ApplicationStatus.INVITED,
        ):
            return
        application.status = status
        application.status_changed_at = now()
        if status == ApplicationStatus.REJECTED:
            application.employer_message = message

    def _set_stage(
        self,
        process: HiringProcess,
        stage: HiringStage,
        actor_id: uuid.UUID,
        comment: str | None,
        role: str = EMPLOYER,
    ) -> None:
        previous = process.stage
        process.stage = stage
        process.stage_changed_at = now()
        self._event(
            process,
            "stage_changed",
            actor_id,
            role,
            data={"from": previous, "to": stage.value},
            comment=comment,
            visible=True,
        )

    def _advance(
        self,
        process: HiringProcess,
        stage: HiringStage,
        actor_id: uuid.UUID,
        role: str,
    ) -> None:
        """Переводит на этап, только если кандидат ещё до него не дошёл."""
        if STAGE_ORDER.index(HiringStage(process.stage)) < STAGE_ORDER.index(stage):
            self._set_stage(process, stage, actor_id, None, role)

    def _finish(
        self,
        process: HiringProcess,
        status: HiringStatus,
        actor_id: uuid.UUID,
        role: str,
        *,
        comment: str | None = None,
        internal_reason: str | None = None,
        quiet: bool = False,
    ) -> HiringEvent:
        """Завершение процесса: отменяет интервью и отзывает оффер.

        ``quiet`` — без уведомлений и сообщений в переписку (их отправил
        вызывающий).
        """
        process.status = status
        process.closed_at = now()
        for interview in process.interviews:
            if interview.status == InterviewStatus.SCHEDULED:
                interview.status = InterviewStatus.CANCELLED
        offer = active_offer(process)
        if offer is not None:
            offer.status = OfferStatus.WITHDRAWN
            offer.responded_at = now()
        event_type = {
            HiringStatus.HIRED: "hired",
            HiringStatus.REJECTED: "rejected",
            HiringStatus.WITHDRAWN: "withdrawn",
        }[status]
        event = self._event(
            process, event_type, actor_id, role, comment=comment, visible=True
        )
        if internal_reason:
            # Причина отказа — внутренняя заметка, кандидат её не видит.
            self._event(
                process,
                "comment",
                actor_id,
                role,
                data={"rejection_reason": True},
                comment=internal_reason,
            )
        if quiet:
            return event
        if status == HiringStatus.REJECTED and role == EMPLOYER:
            self._tell_candidate(
                process,
                event,
                f"Решение по вакансии «{process.vacancy_title}»",
                f"{process.company_name} не готов продолжить с вами процесс найма."
                + (f"\n\n{comment}" if comment else ""),
                chat_status="rejected",
            )
        elif status == HiringStatus.WITHDRAWN:
            self._chat(process, event, "Кандидат вышел из процесса найма.", "withdrawn")
        return event

    def _event(
        self,
        process: HiringProcess,
        type: str,
        actor_id: uuid.UUID | None,
        role: str,
        *,
        data: dict[str, Any] | None = None,
        comment: str | None = None,
        visible: bool = False,
    ) -> HiringEvent:
        event = HiringEvent(
            id=uuid.uuid4(),
            type=type,
            actor_id=actor_id,
            actor_role=role,
            data=data or {},
            comment=comment,
            visible_to_candidate=visible,
            created_at=now(),
        )
        process.events.append(event)
        return event

    @staticmethod
    def _interview(process: HiringProcess, interview_id: uuid.UUID) -> Interview:
        interview = next((i for i in process.interviews if i.id == interview_id), None)
        if interview is None:
            raise NotFoundError("Интервью не найдено", code="interview_not_found")
        return interview

    @staticmethod
    def _offer(process: HiringProcess, offer_id: uuid.UUID) -> JobOffer:
        offer = next((o for o in process.offers if o.id == offer_id), None)
        if offer is None:
            raise NotFoundError("Оффер не найден", code="offer_not_found")
        return offer

    @staticmethod
    def _ensure_offer_pending(offer: JobOffer) -> None:
        if offer.status != OfferStatus.SENT:
            raise ConflictError(
                "Оффер уже не ожидает ответа", code=f"offer_{offer.status}"
            )

    @staticmethod
    def _interview_data(interview: Interview) -> dict[str, Any]:
        return {
            "interview_id": str(interview.id),
            "kind": interview.kind,
            "scheduled_at": interview.scheduled_at.isoformat(),
            "duration_minutes": interview.duration_minutes,
            "format": interview.format,
        }

    @staticmethod
    def _offer_data(offer: JobOffer) -> dict[str, Any]:
        return {
            "offer_id": str(offer.id),
            "salary": offer.salary,
            "currency": offer.currency,
            "expires_at": offer.expires_at.isoformat(),
        }

    # --- Уведомления и переписка ------------------------------------------------------

    def _tell_candidate(
        self,
        process: HiringProcess,
        event: HiringEvent,
        title: str,
        body: str,
        *,
        email: bool = True,
        chat_status: str | None = None,
    ) -> None:
        self._notify(process, process.candidate_id, event, title, body, email=email)
        self._chat(process, event, body, chat_status)

    def _tell_employer(
        self, process: HiringProcess, event: HiringEvent, title: str, body: str
    ) -> None:
        self._notify(process, process.employer_id, event, title, body, email=True)
        if event.type not in ("withdrawn",):
            self._chat(process, event, body, None)

    def _notify(
        self,
        process: HiringProcess,
        user_id: uuid.UUID,
        event: HiringEvent,
        title: str,
        body: str,
        *,
        email: bool,
    ) -> None:
        enqueue(
            self.session,
            OutboxMessage,
            NOTIFICATION,
            {
                "user_id": str(user_id),
                "type": f"hiring.{event.type}",
                # Лимиты notification-service: длинное название вакансии не
                # должно приводить к потере уведомления.
                "title": title[:200],
                "body": body[:5000],
                "link": f"/hiring/{process.id}",
                "data": {
                    "process_id": str(process.id),
                    "vacancy_title": process.vacancy_title,
                    "stage": process.stage,
                    "status": process.status,
                },
                "email": email,
                "dedup_key": f"hiring.{event.type}:{event.id}",
            },
        )

    def _chat(
        self,
        process: HiringProcess,
        event: HiringEvent,
        text: str,
        status: str | None,
    ) -> None:
        """Системное сообщение в переписке по отклику или приглашению.

        ``status`` закрывает переписку (rejected, withdrawn); иначе статус
        источника не меняется.
        """
        source_status = self._source_status.get(process.id) or (
            "accepted" if process.source == HiringSource.INVITATION else "new"
        )
        enqueue(
            self.session,
            OutboxMessage,
            CHAT_SYNC,
            {
                "source": process.source,
                "invitation_id": str(process.source_id),
                "candidate_id": str(process.candidate_id),
                "employer_id": str(process.employer_id),
                "vacancy_title": process.vacancy_title,
                "company_name": process.company_name,
                "invitation_status": status or source_status,
                "event_text": text,
                "event_key": f"hiring:{event.id}",
            },
        )
