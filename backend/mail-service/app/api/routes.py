"""HTTP API mail-service. Доступно только другим сервисам (внутренний токен)."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

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
