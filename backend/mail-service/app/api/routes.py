"""HTTP API mail-service. Доступно только другим сервисам (внутренний токен)."""

import hmac
import html
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, HttpUrl

from app.core.config import settings
from app.services.sender import MailSender, MailSendError, get_sender
from app.services.templates import render


def verify_internal_token(
    x_internal_token: Annotated[str, Header()] = "",
) -> None:
    if not hmac.compare_digest(x_internal_token, settings.internal_api_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


health_router = APIRouter(tags=["health"])
router = APIRouter(
    prefix="/emails",
    tags=["emails"],
    dependencies=[Depends(verify_internal_token)],
)

SenderDep = Annotated[MailSender, Depends(get_sender)]


class VerificationCodeEmail(BaseModel):
    to: EmailStr
    code: str = Field(pattern=r"^\d{4,8}$")
    ttl_minutes: int = Field(gt=0, le=1440)


class NotificationEmail(BaseModel):
    """Письмо-уведомление: приглашение, результат тестирования и т. п."""

    to: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    action_url: HttpUrl | None = None
    action_label: str = Field(default="Открыть", max_length=60)


class SendResult(BaseModel):
    status: str = "sent"


@health_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/verification-code",
    response_model=SendResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_verification_code(
    data: VerificationCodeEmail, sender: SenderDep
) -> SendResult:
    message = render(
        "verification_code",
        to=str(data.to),
        subject=f"Benefit: код подтверждения {data.code}",
        params={"code": data.code, "ttl_minutes": data.ttl_minutes},
    )
    try:
        await sender.send(message)
    except MailSendError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Почтовый сервер недоступен",
        ) from exc
    return SendResult()


@router.post(
    "/notification",
    response_model=SendResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_notification(data: NotificationEmail, sender: SenderDep) -> SendResult:
    action_text, action_html = "", ""
    if data.action_url:
        url = str(data.action_url)
        action_text = f"\n{data.action_label}: {url}\n"
        label = html.escape(data.action_label)
        action_html = (
            f'<a href="{html.escape(url)}" style="display:inline-block;'
            "background:#2563eb;color:#ffffff;text-decoration:none;"
            f'padding:10px 18px;border-radius:8px;">{label}</a>'
        )
    message = render(
        "notification",
        to=str(data.to),
        subject=data.subject,
        params={"title": data.title, "body": data.body, "action_text": action_text},
        raw_html={"action_html": action_html},
    )
    try:
        await sender.send(message)
    except MailSendError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Почтовый сервер недоступен",
        ) from exc
    return SendResult()
