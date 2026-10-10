"""Процесс найма (``/api/v1/hiring``).

Работодатель: воронка, этапы, ответственные, интервью, офферы, история.
Кандидат: свои процессы, ответ на оффер, выход из процесса.
"""

import uuid
from typing import Annotated

from benefit_common.security import Candidate, Employer
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep
from app.models import (
    HiringProcess,
    HiringStage,
    HiringStatus,
    Interview,
    TeamMember,
)
from app.schemas.hiring import (
    CandidateInterviewResponse,
    CandidateProcess,
    CandidateReply,
    CommentCreate,
    EmployerEventResponse,
    EventResponse,
    HiringDictionaries,
    InterviewCancel,
    InterviewCreate,
    InterviewResponse,
    InterviewResult,
    InterviewUpdate,
    OfferCreate,
    OfferResponse,
    Option,
    PersonBrief,
    ProcessDetail,
    ProcessSummary,
    RejectRequest,
    ResponsibleUpdate,
    StageChange,
    TeamMemberIn,
    TeamMemberResponse,
    TeamMemberUpdate,
)
from app.services import hiring as h
from app.services.hiring import HiringService

router = APIRouter(tags=["hiring: процесс найма"])


def get_service(session: SessionDep) -> HiringService:
    return HiringService(session)


ServiceDep = Annotated[HiringService, Depends(get_service)]


# --- Представление --------------------------------------------------------------------


def _person(member: TeamMember | None) -> PersonBrief | None:
    return PersonBrief.model_validate(member) if member else None


async def _people(
    service: HiringService, process: HiringProcess
) -> dict[uuid.UUID, TeamMember]:
    ids = {i for interview in process.interviews for i in interview.interviewer_ids}
    return await service.members(process.employer_id, ids)


def _summary_fields(process: HiringProcess) -> dict:
    upcoming = h.next_interview(process)
    last_offer = process.offers[-1] if process.offers else None
    return {
        "id": process.id,
        "candidate_id": process.candidate_id,
        "source": process.source,
        "source_id": process.source_id,
        "vacancy_id": process.vacancy_id,
        "vacancy_title": process.vacancy_title,
        "company_name": process.company_name,
        "stage": process.stage,
        "status": process.status,
        "responsible": _person(process.responsible),
        "next_interview_at": upcoming.scheduled_at if upcoming else None,
        "offer_status": last_offer.status if last_offer else None,
        "stage_changed_at": process.stage_changed_at,
        "closed_at": process.closed_at,
        "created_at": process.created_at,
        "updated_at": process.updated_at,
    }


def _interview_fields(
    interview: Interview, people: dict[uuid.UUID, TeamMember]
) -> dict:
    return {
        "id": interview.id,
        "kind": interview.kind,
        "title": interview.title,
        "scheduled_at": interview.scheduled_at,
        "duration_minutes": interview.duration_minutes,
        "format": interview.format,
        "location": interview.location,
        "interviewers": [
            _person(people[i]) for i in interview.interviewer_ids if i in people
        ],
        "note_for_candidate": interview.note_for_candidate,
        "status": interview.status,
    }


async def employer_view(
    service: HiringService, process: HiringProcess
) -> ProcessDetail:
    people = await _people(service, process)
    return ProcessDetail(
        **_summary_fields(process),
        rejection_reason=process.rejection_reason,
        interviews=[
            InterviewResponse(
                **_interview_fields(i, people),
                rating=i.rating,
                feedback=i.feedback,
                completed_at=i.completed_at,
                created_at=i.created_at,
            )
            for i in process.interviews
        ],
        offers=[OfferResponse.model_validate(o) for o in process.offers],
        history=[EmployerEventResponse.model_validate(e) for e in process.events],
    )


async def candidate_view(
    service: HiringService, process: HiringProcess
) -> CandidateProcess:
    people = await _people(service, process)
    return CandidateProcess(
        id=process.id,
        employer_id=process.employer_id,
        source=process.source,
        source_id=process.source_id,
        vacancy_id=process.vacancy_id,
        vacancy_title=process.vacancy_title,
        company_name=process.company_name,
        stage=process.stage,
        status=process.status,
        responsible=_person(process.responsible),
        interviews=[
            CandidateInterviewResponse(**_interview_fields(i, people))
            for i in process.interviews
        ],
        offers=[OfferResponse.model_validate(o) for o in process.offers],
        # Внутренние заметки, оценки и смена ответственного кандидату не видны.
        history=[
            EventResponse.model_validate(e)
            for e in process.events
            if e.visible_to_candidate
        ],
        closed_at=process.closed_at,
        created_at=process.created_at,
        updated_at=process.updated_at,
    )


# --- Справочники ----------------------------------------------------------------------


def _options(titles: dict) -> list[Option]:
    return [Option(id=str(k), title=v) for k, v in titles.items()]


@router.get("/dictionaries", response_model=HiringDictionaries)
async def dictionaries() -> HiringDictionaries:
    """Подписи этапов, статусов и типов событий для интерфейса."""
    return HiringDictionaries(
        stages=_options(h.STAGE_TITLES),
        statuses=_options(h.STATUS_TITLES),
        interview_kinds=_options(h.INTERVIEW_KIND_TITLES),
        interview_formats=_options(h.INTERVIEW_FORMAT_TITLES),
        interview_statuses=_options(h.INTERVIEW_STATUS_TITLES),
        offer_statuses=_options(h.OFFER_STATUS_TITLES),
        event_types=_options(h.EVENT_TITLES),
    )


# --- Работодатель: команда ------------------------------------------------------------


@router.get("/team", response_model=list[TeamMemberResponse], tags=["hiring: команда"])
async def list_team(
    employer: Employer,
    service: ServiceDep,
    include_inactive: bool = False,
) -> list[TeamMember]:
    """Сотрудники, участвующие в найме: ответственные и интервьюеры."""
    return await service.team(employer, include_inactive)


@router.post(
    "/team",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["hiring: команда"],
)
async def add_team_member(
    data: TeamMemberIn, employer: Employer, service: ServiceDep
) -> TeamMember:
    return await service.add_member(employer, data)


@router.patch(
    "/team/{member_id}", response_model=TeamMemberResponse, tags=["hiring: команда"]
)
async def update_team_member(
    member_id: uuid.UUID,
    data: TeamMemberUpdate,
    employer: Employer,
    service: ServiceDep,
) -> TeamMember:
    """Изменение данных; ``is_active: false`` — убрать из команды (история
    и прошлые назначения сохраняются)."""
    return await service.update_member(employer, member_id, data)


# --- Работодатель: воронка и карточка -------------------------------------------------


@router.get("/processes", response_model=list[ProcessSummary])
async def list_processes(
    employer: Employer,
    service: ServiceDep,
    status: HiringStatus | None = None,
    stage: HiringStage | None = None,
    vacancy_id: Annotated[str | None, Query(max_length=64)] = None,
    responsible_id: uuid.UUID | None = None,
    candidate_id: uuid.UUID | None = None,
) -> list[ProcessSummary]:
    """Воронка работодателя с фильтрами (по умолчанию — все процессы)."""
    processes = await service.employer_list(
        employer,
        status=status,
        stage=stage,
        vacancy_id=vacancy_id,
        responsible_id=responsible_id,
        candidate_id=candidate_id,
    )
    return [ProcessSummary(**_summary_fields(p)) for p in processes]


@router.get("/processes/{process_id}", response_model=ProcessDetail)
async def get_process(
    process_id: uuid.UUID, employer: Employer, service: ServiceDep
) -> ProcessDetail:
    """Карточка процесса: интервью с оценками, офферы и полная история."""
    process = await service.get(employer, process_id)
    if process.employer_id != employer.id:
        raise h.not_found()
    return await employer_view(service, process)


@router.post("/processes/{process_id}/stage", response_model=ProcessDetail)
async def change_stage(
    process_id: uuid.UUID, data: StageChange, employer: Employer, service: ServiceDep
) -> ProcessDetail:
    """Перевод на этап (вперёд или назад). «Нанят» — только через оффер."""
    process = await service.change_stage(employer, process_id, data)
    return await employer_view(service, process)


@router.put("/processes/{process_id}/responsible", response_model=ProcessDetail)
async def set_responsible(
    process_id: uuid.UUID,
    data: ResponsibleUpdate,
    employer: Employer,
    service: ServiceDep,
) -> ProcessDetail:
    process = await service.set_responsible(employer, process_id, data)
    return await employer_view(service, process)


@router.post("/processes/{process_id}/comments", response_model=ProcessDetail)
async def add_comment(
    process_id: uuid.UUID, data: CommentCreate, employer: Employer, service: ServiceDep
) -> ProcessDetail:
    """Внутренняя заметка в истории (кандидат не видит)."""
    process = await service.comment(employer, process_id, data)
    return await employer_view(service, process)


@router.post("/processes/{process_id}/reject", response_model=ProcessDetail)
async def reject(
    process_id: uuid.UUID, data: RejectRequest, employer: Employer, service: ServiceDep
) -> ProcessDetail:
    """Отказ: интервью отменяются, оффер отзывается, переписка закрывается."""
    process = await service.reject(employer, process_id, data)
    return await employer_view(service, process)


@router.post(
    "/processes/{process_id}/interviews",
    response_model=ProcessDetail,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_interview(
    process_id: uuid.UUID,
    data: InterviewCreate,
    employer: Employer,
    service: ServiceDep,
) -> ProcessDetail:
    """Назначить интервью. Кандидат получит уведомление и письмо."""
    process = await service.schedule_interview(employer, process_id, data)
    return await employer_view(service, process)


@router.patch(
    "/processes/{process_id}/interviews/{interview_id}", response_model=ProcessDetail
)
async def update_interview(
    process_id: uuid.UUID,
    interview_id: uuid.UUID,
    data: InterviewUpdate,
    employer: Employer,
    service: ServiceDep,
) -> ProcessDetail:
    """Перенос или изменение назначенного интервью."""
    process = await service.update_interview(employer, process_id, interview_id, data)
    return await employer_view(service, process)


@router.post(
    "/processes/{process_id}/interviews/{interview_id}/cancel",
    response_model=ProcessDetail,
)
async def cancel_interview(
    process_id: uuid.UUID,
    interview_id: uuid.UUID,
    employer: Employer,
    service: ServiceDep,
    data: InterviewCancel | None = None,
) -> ProcessDetail:
    process = await service.cancel_interview(
        employer, process_id, interview_id, data or InterviewCancel()
    )
    return await employer_view(service, process)


@router.post(
    "/processes/{process_id}/interviews/{interview_id}/result",
    response_model=ProcessDetail,
)
async def record_interview_result(
    process_id: uuid.UUID,
    interview_id: uuid.UUID,
    data: InterviewResult,
    employer: Employer,
    service: ServiceDep,
) -> ProcessDetail:
    """Итог интервью: проведено / не пришёл, оценка 1–5 и отзыв."""
    process = await service.record_result(employer, process_id, interview_id, data)
    return await employer_view(service, process)


@router.post(
    "/processes/{process_id}/offers",
    response_model=ProcessDetail,
    status_code=status.HTTP_201_CREATED,
)
async def make_offer(
    process_id: uuid.UUID, data: OfferCreate, employer: Employer, service: ServiceDep
) -> ProcessDetail:
    """Отправить оффер. Одновременно ждёт ответа только один оффер."""
    process = await service.make_offer(employer, process_id, data)
    return await employer_view(service, process)


@router.post(
    "/processes/{process_id}/offers/{offer_id}/withdraw",
    response_model=ProcessDetail,
)
async def withdraw_offer(
    process_id: uuid.UUID,
    offer_id: uuid.UUID,
    employer: Employer,
    service: ServiceDep,
) -> ProcessDetail:
    process = await service.withdraw_offer(employer, process_id, offer_id)
    return await employer_view(service, process)


# --- Кандидат -------------------------------------------------------------------------


@router.get("/my", response_model=list[CandidateProcess], tags=["hiring: кандидат"])
async def my_processes(
    candidate: Candidate, service: ServiceDep
) -> list[CandidateProcess]:
    """Процессы найма кандидата: этап, интервью, офферы, история."""
    processes = await service.candidate_list(candidate)
    return [await candidate_view(service, p) for p in processes]


@router.get(
    "/my/{process_id}", response_model=CandidateProcess, tags=["hiring: кандидат"]
)
async def my_process(
    process_id: uuid.UUID, candidate: Candidate, service: ServiceDep
) -> CandidateProcess:
    process = await service.get(candidate, process_id)
    if process.candidate_id != candidate.id:
        raise h.not_found()
    return await candidate_view(service, process)


@router.post(
    "/my/{process_id}/offers/{offer_id}/accept",
    response_model=CandidateProcess,
    tags=["hiring: кандидат"],
)
async def accept_offer(
    process_id: uuid.UUID,
    offer_id: uuid.UUID,
    candidate: Candidate,
    service: ServiceDep,
    data: CandidateReply | None = None,
) -> CandidateProcess:
    """Принять оффер: процесс завершается со статусом «Нанят»."""
    process = await service.accept_offer(
        candidate, process_id, offer_id, data or CandidateReply()
    )
    return await candidate_view(service, process)


@router.post(
    "/my/{process_id}/offers/{offer_id}/decline",
    response_model=CandidateProcess,
    tags=["hiring: кандидат"],
)
async def decline_offer(
    process_id: uuid.UUID,
    offer_id: uuid.UUID,
    candidate: Candidate,
    service: ServiceDep,
    data: CandidateReply | None = None,
) -> CandidateProcess:
    process = await service.decline_offer(
        candidate, process_id, offer_id, data or CandidateReply()
    )
    return await candidate_view(service, process)


@router.post(
    "/my/{process_id}/withdraw",
    response_model=CandidateProcess,
    tags=["hiring: кандидат"],
)
async def withdraw(
    process_id: uuid.UUID,
    candidate: Candidate,
    service: ServiceDep,
    data: CandidateReply | None = None,
) -> CandidateProcess:
    """Выйти из процесса найма (отклик, если он был, тоже отзывается)."""
    process = await service.candidate_withdraw(
        candidate, process_id, data or CandidateReply()
    )
    return await candidate_view(service, process)
