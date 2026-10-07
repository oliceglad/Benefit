from typing import Annotated

from fastapi import APIRouter, Depends
from httpx import AsyncClient

from app.api.deps import require_roles
from app.main import app
from app.models.user import User, UserRole
from tests.conftest import FakeMailClient
from tests.test_auth import register_and_verify

# Тестовый эндпоинт, доступный только работодателям.
_router = APIRouter()


@_router.get("/_test/employer-only")
async def employer_only(
    user: Annotated[User, Depends(require_roles(UserRole.EMPLOYER))],
) -> dict[str, str]:
    return {"email": user.email}


app.include_router(_router)


async def test_require_roles(client: AsyncClient, mail: FakeMailClient) -> None:
    employer = await register_and_verify(client, mail, "hr@company.ru", "employer")
    candidate = await register_and_verify(client, mail, "dev@mail.ru", "candidate")

    allowed = await client.get(
        "/_test/employer-only",
        headers={"Authorization": f"Bearer {employer['access_token']}"},
    )
    denied = await client.get(
        "/_test/employer-only",
        headers={"Authorization": f"Bearer {candidate['access_token']}"},
    )

    assert allowed.status_code == 200
    assert denied.status_code == 403
