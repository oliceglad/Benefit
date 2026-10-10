"""Отклики кандидатов на вакансии.

Отклик, как и принятое приглашение, открывает работодателю контакты
кандидата и создаёт переписку. Кандидат видит только свои отклики,
работодатель — только отклики на свои вакансии.
"""

import uuid
from datetime import UTC, datetime

from benefit_common.errors import AppError, ConflictError, NotFoundError
from benefit_common.outbox import enqueue
from benefit_common.security import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Application, ApplicationStatus, HiringSource, OutboxMessage
from app.schemas.application import ApplicationCreate, ApplicationStatusUpdate
from app.services.candidates import CandidateDirectory
from app.services.delivery import CHAT_SYNC, CONTACT_GRANT, NOTIFICATION
from app.services.employers import EmployerDirectory
from app.services.hiring import HiringService
from app.services.invitations import format_salary

ACTIVE = (ApplicationStatus.NEW, ApplicationStatus.VIEWED, ApplicationStatus.INVITED)
# Допустимые переходы статуса работодателем.
TRANSITIONS = {
    ApplicationStatus.NEW: {"viewed", "invited", "rejected"},
    ApplicationStatus.VIEWED: {"invited", "rejected"},
    ApplicationStatus.INVITED: {"rejected"},
}
STATUS_TEXT = {
    "viewed": "Работодатель посмотрел ваш отклик",
    "invited": "Работодатель приглашает на собеседование",
    "rejected": "Работодатель отказал по отклику",
}


def _not_found() -> NotFoundError:
    return NotFoundError("Отклик не найден", code="application_not_found")


class ApplicationService:
    def __init__(
        self,
        session: AsyncSession,
        candidates: CandidateDirectory,
        employers: EmployerDirectory,
    ) -> None:
        self.session = session
        self.candidates = candidates
        self.employers = employers
        self.hiring = HiringService(session)

    async def apply(self, candidate: Principal, data: ApplicationCreate) -> Application:
        vacancy = await self.employers.vacancy(data.vacancy_id)
        if vacancy is None or vacancy["status"] != "published":
            raise NotFoundError("Вакансия не найдена", code="vacancy_not_found")
        if await self.candidates.snapshot(candidate.id) is None:
            raise ConflictError(
                "Сначала заполните профиль кандидата", code="profile_required"
            )
        duplicate = await self.session.scalar(
            select(Application.id).where(
                Application.candidate_id == candidate.id,
                Application.vacancy_id == data.vacancy_id,
                Application.status.in_(ACTIVE),
            )
        )
        if duplicate is not None:
            raise ConflictError("Вы уже откликнулись", code="already_applied")

        application = Application(
            vacancy_id=data.vacancy_id,
            employer_id=uuid.UUID(vacancy["owner_id"]),
            candidate_id=candidate.id,
            vacancy_title=vacancy["title"],
            company_name=vacancy["company"]["name"],
            company_id=uuid.UUID(vacancy["company"]["id"]),
            salary_from=vacancy["salary_from"],
            salary_to=vacancy["salary_to"],
            currency=vacancy["currency"],
            salary_type=vacancy.get("salary_type", "gross"),
            cover_letter=data.cover_letter,
            status=ApplicationStatus.NEW,
        )
        self.session.add(application)
        await self.session.flush()
        # Отклик начинает процесс найма (этап «Новый»).
        await self.hiring.open(
            source=HiringSource.APPLICATION,
            source_id=application.id,
            employer_id=application.employer_id,
            candidate_id=candidate.id,
            vacancy_id=str(application.vacancy_id),
            vacancy_title=application.vacancy_title,
            company_name=application.company_name,
            company_id=application.company_id,
            actor_id=candidate.id,
        )
        # Кандидат откликнулся сам — работодатель видит его контакты.
        enqueue(
            self.session,
            OutboxMessage,
            CONTACT_GRANT,
            {
                "candidate_id": str(candidate.id),
                "employer_id": str(application.employer_id),
                "source": "application",
                "source_id": str(application.id),
            },
        )
        text = f"Кандидат откликнулся на вакансию «{application.vacancy_title}»."
        if data.cover_letter:
            text += f"\n\nСопроводительное письмо:\n{data.cover_letter}"
        self._sync_chat(application, "created", text)
        self._notify(
            application,
            application.employer_id,
            "application.received",
            f"Новый отклик: «{application.vacancy_title}»",
            text + "\n\nКонтакты кандидата доступны в его профиле.",
            link=f"/candidates/{candidate.id}",
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def mine(self, candidate: Principal) -> list[Application]:
        return await self._list(Application.candidate_id == candidate.id)

    async def received(
        self,
        employer: Principal,
        vacancy_id: uuid.UUID | None,
        status: ApplicationStatus | None,
    ) -> list[Application]:
        conditions = [Application.employer_id == employer.id]
        if vacancy_id is not None:
            conditions.append(Application.vacancy_id == vacancy_id)
        if status is not None:
            conditions.append(Application.status == status)
        return await self._list(*conditions)

    async def get(self, principal: Principal, application_id: uuid.UUID) -> Application:
        application = await self.session.get(Application, application_id)
        if application is None or principal.id not in (
            application.candidate_id,
            application.employer_id,
        ):
            raise _not_found()
        return application

    async def withdraw(
        self, candidate: Principal, application_id: uuid.UUID
    ) -> Application:
        application = await self.get(candidate, application_id)
        if application.candidate_id != candidate.id:
            raise _not_found()
        self._ensure_active(application)
        application.status = ApplicationStatus.WITHDRAWN
        application.status_changed_at = datetime.now(UTC)
        await self.hiring.on_application_status(application, candidate)
        self._sync_chat(application, "withdrawn", "Кандидат отозвал отклик.")
        self._notify(
            application,
            application.employer_id,
            "application.withdrawn",
            f"Отклик отозван: «{application.vacancy_title}»",
            "Кандидат отозвал свой отклик.",
            email=False,
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def set_status(
        self,
        employer: Principal,
        application_id: uuid.UUID,
        data: ApplicationStatusUpdate,
    ) -> Application:
        application = await self.get(employer, application_id)
        if application.employer_id != employer.id:
            raise _not_found()
        allowed = TRANSITIONS.get(ApplicationStatus(application.status), set())
        if data.status not in allowed:
            raise AppError(
                "Такой переход статуса невозможен",
                code=f"application_{application.status}",
                status_code=409,
            )
        application.status = data.status
        application.employer_message = data.message
        application.status_changed_at = datetime.now(UTC)
        await self.hiring.on_application_status(application, employer)
        text = f"{STATUS_TEXT[data.status]} («{application.vacancy_title}»)."
        if data.message:
            text += f"\n\n{data.message}"
        if data.status != "viewed":
            self._sync_chat(application, data.status, text)
        self._notify(
            application,
            application.candidate_id,
            f"application.{data.status}",
            STATUS_TEXT[data.status],
            text,
            link=f"/applications/{application.id}",
            email=data.status != "viewed",
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def _list(self, *conditions: object) -> list[Application]:
        result = await self.session.scalars(
            select(Application)
            .where(*conditions)
            .order_by(Application.created_at.desc())
        )
        return list(result)

    @staticmethod
    def _ensure_active(application: Application) -> None:
        if application.status not in ACTIVE:
            raise ConflictError(
                "Отклик уже закрыт", code=f"application_{application.status}"
            )

    def _sync_chat(self, application: Application, event: str, text: str) -> None:
        """Переписка по отклику: создаётся с откликом, закрывается при
        отказе или отзыве."""
        enqueue(
            self.session,
            OutboxMessage,
            CHAT_SYNC,
            {
                "source": "application",
                "invitation_id": str(application.id),
                "candidate_id": str(application.candidate_id),
                "employer_id": str(application.employer_id),
                "vacancy_title": application.vacancy_title,
                "company_name": application.company_name,
                "invitation_status": application.status,
                "event_text": text,
                "event_key": f"application:{event}",
            },
        )

    def _notify(
        self,
        application: Application,
        user_id: uuid.UUID,
        event: str,
        title: str,
        body: str,
        *,
        link: str | None = None,
        email: bool = True,
    ) -> None:
        enqueue(
            self.session,
            OutboxMessage,
            NOTIFICATION,
            {
                "user_id": str(user_id),
                "type": event,
                "title": title,
                "body": body,
                "link": link or f"/applications/{application.id}",
                "data": {
                    "application_id": str(application.id),
                    "vacancy_id": str(application.vacancy_id),
                    "salary": format_salary(application),
                },
                "email": email,
                "dedup_key": f"{event}:{application.id}",
            },
        )
