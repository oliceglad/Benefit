"""Приглашения работодателей кандидатам.

Кандидат видит только адресованные ему приглашения, работодатель — только
отправленные им. Чужие приглашения неотличимы от несуществующих (404).
"""

import uuid
from datetime import UTC, datetime, timedelta

from benefit_common.errors import AppError, ConflictError, NotFoundError
from benefit_common.outbox import enqueue
from benefit_common.security import Principal
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Invitation, InvitationStatus, OutboxMessage
from app.schemas.invitation import (
    InvitationCreate,
    InvitationReply,
    InvitationResponse,
    Offer,
    Vacancy,
)
from app.services.candidates import CandidateDirectory
from app.services.delivery import CHAT_SYNC, CONTACT_GRANT, NOTIFICATION
from app.services.employers import EmployerDirectory

CURRENCY_SIGNS = {"RUB": "₽", "USD": "$", "EUR": "€"}


def format_salary(invitation: Invitation) -> str:
    sign = CURRENCY_SIGNS.get(invitation.currency, invitation.currency)

    def money(value: int) -> str:
        return f"{value:,}".replace(",", " ")

    low, high = invitation.salary_from, invitation.salary_to
    if low and high:
        return f"{money(low)} – {money(high)} {sign}"
    if low:
        return f"от {money(low)} {sign}"
    if high:
        return f"до {money(high)} {sign}"
    return "по договорённости"


def to_response(invitation: Invitation) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        status=invitation.status,
        candidate_id=invitation.candidate_id,
        employer_id=invitation.employer_id,
        vacancy=Vacancy(
            vacancy_id=invitation.vacancy_id,
            title=invitation.vacancy_title,
            company_name=invitation.company_name,
            salary_from=invitation.salary_from,
            salary_to=invitation.salary_to,
            currency=invitation.currency,
            work_format=invitation.work_format,
            city=invitation.city,
        ),
        message=invitation.message,
        response_message=invitation.response_message,
        created_at=invitation.created_at,
        responded_at=invitation.responded_at,
        expires_at=invitation.expires_at,
    )


class InvitationService:
    def __init__(
        self,
        session: AsyncSession,
        candidates: CandidateDirectory,
        employers: EmployerDirectory,
    ) -> None:
        self.session = session
        self.candidates = candidates
        self.employers = employers

    async def create(self, employer: Principal, data: InvitationCreate) -> Invitation:
        snapshot = await self.candidates.snapshot(data.candidate_id)
        # Черновики и скрытые профили не раскрываем: для работодателя их нет.
        if snapshot is None or snapshot.get("status") != "published":
            raise NotFoundError("Кандидат не найден", code="candidate_not_found")

        sent_today = await self.session.scalar(
            select(func.count()).where(
                Invitation.employer_id == employer.id,
                Invitation.created_at > datetime.now(UTC) - timedelta(days=1),
            )
        )
        if (sent_today or 0) >= settings.invitations_per_day:
            raise AppError(
                f"Можно отправить не больше {settings.invitations_per_day} "
                "приглашений в сутки",
                code="invitation_limit",
                status_code=429,
            )
        offer = await self._resolve_offer(employer, data.vacancy)
        duplicate = await self.session.scalar(
            select(Invitation.id).where(
                Invitation.employer_id == employer.id,
                Invitation.candidate_id == data.candidate_id,
                Invitation.status == InvitationStatus.PENDING,
                Invitation.expires_at > datetime.now(UTC),
                func.lower(Invitation.vacancy_title) == offer.title.lower(),
            )
        )
        if duplicate is not None:
            raise ConflictError(
                "Кандидат уже приглашён на эту вакансию", code="already_invited"
            )

        invitation = Invitation(
            employer_id=employer.id,
            candidate_id=data.candidate_id,
            vacancy_id=offer.vacancy_id,
            vacancy_title=offer.title,
            company_name=offer.company_name,
            salary_from=offer.salary_from,
            salary_to=offer.salary_to,
            currency=offer.currency,
            work_format=offer.work_format,
            city=offer.city,
            message=data.message,
            status=InvitationStatus.PENDING,
            expires_at=datetime.now(UTC) + timedelta(days=settings.invitation_ttl_days),
        )
        self.session.add(invitation)
        await self.session.flush()
        body = (
            f"{invitation.company_name} приглашает вас на вакансию "
            f"«{invitation.vacancy_title}».\nЗарплата: {format_salary(invitation)}."
        )
        if invitation.message:
            body += f"\n\nСообщение работодателя:\n{invitation.message}"
        self._sync_chat(
            invitation,
            "created",
            f"{invitation.company_name} приглашает на вакансию "
            f"«{invitation.vacancy_title}» ({format_salary(invitation)})."
            + (f"\n\n{invitation.message}" if invitation.message else ""),
        )
        self._notify(
            invitation,
            invitation.candidate_id,
            "invitation.received",
            f"Приглашение на вакансию «{invitation.vacancy_title}»",
            body + f"\n\nОтветьте до {invitation.expires_at:%d.%m.%Y}.",
        )
        await self.session.commit()
        await self.session.refresh(invitation)
        return invitation

    async def _resolve_offer(self, employer: Principal, offer: Offer) -> Vacancy:
        """Дополняет предложение данными вакансии и профиля компании."""
        values = offer.model_dump(exclude_none=True)
        if offer.vacancy_id is not None:
            vacancy = await self.employers.vacancy(offer.vacancy_id)
            if vacancy is None or vacancy["owner_id"] != str(employer.id):
                raise NotFoundError("Вакансия не найдена", code="vacancy_not_found")
            values = {
                "title": vacancy["title"],
                "company_name": vacancy["company"]["name"],
                "salary_from": vacancy["salary_from"],
                "salary_to": vacancy["salary_to"],
                "currency": vacancy["currency"],
                "work_format": vacancy["work_format"],
                "city": vacancy["city"],
            } | values
            values["vacancy_id"] = str(offer.vacancy_id)
        if "company_name" not in values:
            company = await self.employers.company(employer.id)
            if company is None:
                raise AppError(
                    "Укажите компанию или заполните профиль компании",
                    code="company_required",
                    status_code=422,
                )
            values["company_name"] = company["name"]
        if "title" not in values:
            raise AppError(
                "Укажите должность или вакансию", code="title_required", status_code=422
            )
        return Vacancy.model_validate(
            {k: v for k, v in values.items() if v is not None}
        )

    async def incoming(
        self, candidate: Principal, status: InvitationStatus | None
    ) -> list[Invitation]:
        return await self._list(Invitation.candidate_id == candidate.id, status)

    async def sent(
        self, employer: Principal, status: InvitationStatus | None
    ) -> list[Invitation]:
        return await self._list(Invitation.employer_id == employer.id, status)

    async def get(self, principal: Principal, invitation_id: uuid.UUID) -> Invitation:
        invitation = await self.session.get(Invitation, invitation_id)
        if invitation is None or principal.id not in (
            invitation.candidate_id,
            invitation.employer_id,
        ):
            raise NotFoundError("Приглашение не найдено", code="invitation_not_found")
        await self._expire([invitation])
        return invitation

    async def respond(
        self,
        candidate: Principal,
        invitation_id: uuid.UUID,
        reply: InvitationReply,
        *,
        accept: bool,
    ) -> Invitation:
        invitation = await self.get(candidate, invitation_id)
        if invitation.candidate_id != candidate.id:
            raise NotFoundError("Приглашение не найдено", code="invitation_not_found")
        self._ensure_pending(invitation)
        invitation.status = (
            InvitationStatus.ACCEPTED if accept else InvitationStatus.DECLINED
        )
        invitation.response_message = reply.message
        invitation.responded_at = datetime.now(UTC)
        verb = "принял" if accept else "отклонил"
        body = f"Кандидат {verb} приглашение на вакансию «{invitation.vacancy_title}»."
        if reply.message:
            body += f"\n\nСообщение кандидата:\n{reply.message}"
        self._sync_chat(
            invitation,
            invitation.status,
            f"Кандидат {verb} приглашение."
            + (f" Комментарий: {reply.message}" if reply.message else ""),
        )
        link = None
        if accept:
            # Принятие приглашения открывает работодателю контакты кандидата.
            enqueue(
                self.session,
                OutboxMessage,
                CONTACT_GRANT,
                {
                    "candidate_id": str(invitation.candidate_id),
                    "employer_id": str(invitation.employer_id),
                    "source": "invitation",
                    "source_id": str(invitation.id),
                },
            )
            body += "\n\nКонтакты кандидата теперь доступны в его профиле."
            link = f"/candidates/{invitation.candidate_id}"
        self._notify(
            invitation,
            invitation.employer_id,
            f"invitation.{invitation.status}",
            f"Ответ на приглашение: «{invitation.vacancy_title}»",
            body,
            link=link,
        )
        await self.session.commit()
        await self.session.refresh(invitation)
        return invitation

    async def withdraw(
        self, employer: Principal, invitation_id: uuid.UUID
    ) -> Invitation:
        invitation = await self.get(employer, invitation_id)
        if invitation.employer_id != employer.id:
            raise NotFoundError("Приглашение не найдено", code="invitation_not_found")
        self._ensure_pending(invitation)
        invitation.status = InvitationStatus.WITHDRAWN
        invitation.responded_at = datetime.now(UTC)
        self._sync_chat(invitation, "withdrawn", "Работодатель отозвал приглашение.")
        self._notify(
            invitation,
            invitation.candidate_id,
            "invitation.withdrawn",
            f"Приглашение отозвано: «{invitation.vacancy_title}»",
            f"{invitation.company_name} отозвал приглашение на вакансию "
            f"«{invitation.vacancy_title}».",
            email=False,
        )
        await self.session.commit()
        await self.session.refresh(invitation)
        return invitation

    async def _list(self, condition: object, status: InvitationStatus | None) -> list:
        invitations = list(
            await self.session.scalars(
                select(Invitation)
                .where(condition)
                .order_by(Invitation.created_at.desc())
            )
        )
        await self._expire(invitations)
        if status is not None:
            invitations = [i for i in invitations if i.status == status]
        return invitations

    async def _expire(self, invitations: list[Invitation]) -> None:
        now = datetime.now(UTC)
        changed = False
        for invitation in invitations:
            if (
                invitation.status == InvitationStatus.PENDING
                and invitation.expires_at <= now
            ):
                invitation.status = InvitationStatus.EXPIRED
                changed = True
        if changed:
            await self.session.commit()
            for invitation in invitations:
                await self.session.refresh(invitation)

    @staticmethod
    def _ensure_pending(invitation: Invitation) -> None:
        if invitation.status != InvitationStatus.PENDING:
            raise AppError(
                "На приглашение уже ответили или оно больше не действует",
                code=f"invitation_{invitation.status}",
                status_code=409,
            )

    def _sync_chat(self, invitation: Invitation, event: str, text: str) -> None:
        """Диалог в chat-service: создаётся с приглашением, закрывается при
        отказе или отзыве. Системное сообщение описывает событие."""
        enqueue(
            self.session,
            OutboxMessage,
            CHAT_SYNC,
            {
                "invitation_id": str(invitation.id),
                "candidate_id": str(invitation.candidate_id),
                "employer_id": str(invitation.employer_id),
                "vacancy_title": invitation.vacancy_title,
                "company_name": invitation.company_name,
                "invitation_status": invitation.status,
                "event_text": text,
                "event_key": event,
            },
        )

    def _notify(
        self,
        invitation: Invitation,
        user_id: uuid.UUID,
        event: str,
        title: str,
        body: str,
        *,
        email: bool = True,
        link: str | None = None,
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
                "link": link or f"/invitations/{invitation.id}",
                "data": {
                    "invitation_id": str(invitation.id),
                    "vacancy_title": invitation.vacancy_title,
                    "salary": format_salary(invitation),
                },
                "email": email,
                "dedup_key": f"{event}:{invitation.id}",
            },
        )
