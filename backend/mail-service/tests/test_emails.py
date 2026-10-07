from collections.abc import AsyncIterator, Iterator
from email.message import EmailMessage

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.services.sender import get_sender


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


@pytest.fixture
def sender() -> Iterator[FakeSender]:
    fake = FakeSender()
    app.dependency_overrides[get_sender] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


PAYLOAD = {"to": "user@mail.ru", "code": "123456", "ttl_minutes": 10}


async def test_rejects_missing_internal_token(
    client: AsyncClient, sender: FakeSender
) -> None:
    response = await client.post("/api/v1/emails/verification-code", json=PAYLOAD)

    assert response.status_code == 401
    assert sender.sent == []


async def test_sends_verification_code(client: AsyncClient, sender: FakeSender) -> None:
    response = await client.post(
        "/api/v1/emails/verification-code",
        json=PAYLOAD,
        headers={"X-Internal-Token": settings.internal_api_token},
    )

    assert response.status_code == 202
    [message] = sender.sent
    assert message["To"] == "user@mail.ru"
    body = message.get_body(("plain",))
    assert body is not None
    assert "123456" in body.get_content()
