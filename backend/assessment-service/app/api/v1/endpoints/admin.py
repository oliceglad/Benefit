"""Управление тестами — только для роли admin.

Ответы на задачи доступны только здесь; кандидатские эндпоинты их
никогда не возвращают.
"""

import uuid
from typing import Annotated

from benefit_common.security import Admin
from fastapi import APIRouter, Query, status

from app.api.deps import SessionDep
from app.schemas.content import (
    ActiveUpdate,
    AdminTestDetail,
    AdminTestSummary,
    ImportReport,
    TestIn,
    TestPack,
)
from app.services.content import ContentService

router = APIRouter(prefix="/admin", tags=["assessments: администрирование"])


@router.get("/tests", response_model=list[AdminTestSummary])
async def list_tests(_: Admin, session: SessionDep) -> list[AdminTestSummary]:
    return await ContentService(session).summaries()


@router.get("/tests/{assessment_id}", response_model=AdminTestDetail)
async def get_test(
    assessment_id: uuid.UUID, _: Admin, session: SessionDep
) -> AdminTestDetail:
    return await ContentService(session).get(assessment_id)


@router.post(
    "/tests", response_model=AdminTestDetail, status_code=status.HTTP_201_CREATED
)
async def create_test(
    data: TestIn, admin: Admin, session: SessionDep
) -> AdminTestDetail:
    return await ContentService(session).create(data, admin.id)


@router.put("/tests/{assessment_id}", response_model=AdminTestDetail)
async def replace_test(
    assessment_id: uuid.UUID, data: TestIn, admin: Admin, session: SessionDep
) -> AdminTestDetail:
    """Заменяет тест целиком. Задачи сопоставляются по ``key``; убранные
    задачи деактивируются (их используют прошлые попытки)."""
    return await ContentService(session).replace(assessment_id, data, admin.id)


@router.patch("/tests/{assessment_id}", response_model=AdminTestDetail)
async def set_active(
    assessment_id: uuid.UUID, data: ActiveUpdate, admin: Admin, session: SessionDep
) -> AdminTestDetail:
    """Опубликовать или снять тест (кандидаты видят только активные)."""
    return await ContentService(session).set_active(
        assessment_id, data.is_active, admin.id
    )


@router.post("/import", response_model=ImportReport)
async def import_pack(
    pack: TestPack,
    admin: Admin,
    session: SessionDep,
    skip_existing: Annotated[
        bool, Query(description="Не изменять тесты, которые уже есть")
    ] = False,
) -> ImportReport:
    return await ContentService(session).import_pack(
        pack, admin.id, skip_existing=skip_existing
    )


@router.get("/export", response_model=TestPack)
async def export_pack(
    _: Admin,
    session: SessionDep,
    ids: Annotated[list[uuid.UUID] | None, Query()] = None,
) -> TestPack:
    """Выгрузка тестов с ответами (для резервной копии или переноса)."""
    return await ContentService(session).export(ids)
