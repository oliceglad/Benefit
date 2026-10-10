"""Построение поискового индекса по ленте событий candidate-service.

Индексатор не интерпретирует события: по любому событию кандидата он
заново запрашивает его поисковый документ. Поэтому порядок и повторы
событий не важны (идемпотентно), а индекс всегда сходится к текущему
состоянию профиля.
"""

import logging
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import CandidateIndex, ConsumerOffset
from app.services.source import CandidateSource

logger = logging.getLogger(__name__)

CONSUMER = "candidate-events"


def _month_index(value: date) -> int:
    return value.year * 12 + value.month - 1


def skill_experience(
    experience: list[dict[str, Any]], today: date | None = None
) -> dict[str, dict[str, Any]]:
    """Сколько месяцев каждый навык был в стеке мест работы и когда
    использовался последний раз (``YYYY-MM``)."""
    today = today or date.today()
    result: dict[str, dict[str, Any]] = {}
    for job in experience:
        if not job.get("start_date"):
            continue
        start = date.fromisoformat(job["start_date"])
        end = date.fromisoformat(job["end_date"]) if job.get("end_date") else today
        months = max(1, _month_index(end) - _month_index(start) + 1)
        for tech in job.get("technologies") or []:
            entry = result.setdefault(tech.lower(), {"months": 0, "last_used": ""})
            entry["months"] += months
            entry["last_used"] = max(entry["last_used"], end.strftime("%Y-%m"))
    return result


def index_row(document: dict[str, Any]) -> dict[str, Any]:
    """Поля индекса из поискового документа candidate-service."""
    category = document.get("category") or {}
    actuality = document.get("actuality") or {}
    skills = document.get("skills") or []
    achievements = document.get("fsp_achievements") or []
    full_name = " ".join(
        part
        for part in (
            document.get("last_name"),
            document.get("first_name"),
            document.get("middle_name"),
        )
        if part
    )
    text_parts = [
        document.get("headline") or "",
        document.get("about") or "",
        " ".join(s["name"] for s in skills),
        " ".join(
            f"{job.get('position', '')} {job.get('description') or ''}"
            for job in document.get("experience") or []
        ),
    ]
    return {
        "user_id": uuid.UUID(document["user_id"]),
        "full_name": full_name or "Кандидат",
        "headline": document.get("headline"),
        "city": document.get("city"),
        "relocation_ready": bool(document.get("relocation_ready")),
        "job_search_status": document.get("job_search_status") or "active",
        "roles": document.get("roles") or [],
        "specialization": category.get("specialization"),
        "grade": category.get("grade"),
        "grade_status": category.get("grade_status") or "not_confirmed",
        "verified_percent": category.get("percent"),
        "test_title": category.get("test_title"),
        "industry": category.get("industry") or document.get("industry"),
        # Подтверждённые тестом навыки участвуют в фильтрах, даже если
        # кандидат не добавил их в стек.
        "skills": list(
            dict.fromkeys(
                [s["name"].lower() for s in skills]
                + [v["skill"].lower() for v in document.get("verified_skills") or []]
            )
        ),
        "skills_display": skills,
        "skill_experience": skill_experience(document.get("experience") or []),
        "verified_skills": {
            item["skill"].lower(): {
                "skill": item["skill"],
                "level": item["level"]["id"],
                "title": item["level"]["title"],
                "percent": item.get("percent"),
            }
            for item in document.get("verified_skills") or []
        },
        "experience_months": document.get("total_experience_months") or 0,
        "work_formats": document.get("work_formats") or [],
        "employment_types": document.get("employment_types") or [],
        "salary_from": document.get("salary_from"),
        "salary_currency": document.get("salary_currency"),
        "fsp_count": len(achievements),
        "fsp_achievements": [
            {
                k: a.get(k)
                for k in (
                    "event",
                    "discipline",
                    "level",
                    "result",
                    "place",
                    "event_date",
                )
            }
            for a in achievements[:5]
        ],
        "last_active_at": datetime.fromisoformat(actuality["last_active_at"]),
        "activity": {
            k: v for k, v in actuality.items() if k.startswith(("tasks_", "employer_"))
        },
        "has_photo": bool(document.get("has_photo")),
        "published_at": (
            datetime.fromisoformat(document["published_at"])
            if document.get("published_at")
            else None
        ),
        "about": document.get("about"),
        "search_text": " ".join(text_parts),
    }


class Indexer:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], source: CandidateSource
    ) -> None:
        self.session_factory = session_factory
        self.source = source

    async def reindex(self, session: AsyncSession, user_id: uuid.UUID) -> bool:
        """Обновляет запись кандидата; ``False`` — убран из индекса."""
        document = await self.source.document(user_id)
        if document is None:
            await session.execute(
                delete(CandidateIndex).where(CandidateIndex.user_id == user_id)
            )
            return False
        row = index_row(document)
        search_text = row.pop("search_text")
        # Русская морфология + простой словарь (для названий технологий).
        row["search_vector"] = func.to_tsvector("russian", search_text).op("||")(
            func.to_tsvector("simple", search_text)
        )
        statement = pg_insert(CandidateIndex).values(**row)
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[CandidateIndex.user_id],
                set_={
                    column: statement.excluded[column]
                    for column in row
                    if column != "user_id"
                }
                | {"indexed_at": func.now()},
            )
        )
        return True

    async def sync_events(self) -> int:
        """Обрабатывает новые события; возвращает их количество."""
        async with self.session_factory() as session:
            offset = await session.get(ConsumerOffset, CONSUMER, with_for_update=True)
            if offset is None:
                offset = ConsumerOffset(name=CONSUMER, last_event_id=0)
                session.add(offset)
                await session.flush()
            events = await self.source.events(
                offset.last_event_id, settings.sync_batch_size
            )
            if not events:
                await session.commit()
                return 0
            # По каждому кандидату достаточно одного переиндексирования.
            for user_id in dict.fromkeys(uuid.UUID(e["aggregate_id"]) for e in events):
                await self.reindex(session, user_id)
            offset.last_event_id = events[-1]["id"]
            await session.commit()
            logger.info(
                "Indexed %s events up to #%s", len(events), offset.last_event_id
            )
            return len(events)

    async def bootstrap(self) -> int:
        """Первичная загрузка всех опубликованных профилей в пустой индекс."""
        async with self.session_factory() as session:
            if await session.scalar(select(func.count()).select_from(CandidateIndex)):
                return 0
            total, page = 0, 200
            while ids := await self.source.published_ids(total, page):
                for user_id in ids:
                    await self.reindex(session, user_id)
                total += len(ids)
                if len(ids) < page:
                    break
            await session.commit()
            logger.info("Bootstrapped index with %s candidates", total)
            return total
