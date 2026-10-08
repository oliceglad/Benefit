"""Поиск по банку кандидатов, подборка по потребности и похожие кандидаты."""

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from benefit_common.dictionaries import GRADE_ORDER, Grade
from benefit_common.skills import related_skills
from sqlalchemy import Select, and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import CandidateIndex
from app.schemas.talent import (
    Actuality,
    CandidateCard,
    Category,
    CategoryCount,
    MatchCriteria,
    MatchedCandidate,
    MatchResult,
    SearchPage,
    SimilarCandidate,
    Suggestion,
)
from app.services.scoring import (
    ACTIVE_DAYS,
    MIN_REQUIRED_COVERAGE,
    Preference,
    category_hint,
    evaluate,
    exclusion_suggestion,
    extract_keywords,
    fit_label,
    hard_filters,
    match_skills,
    required_coverage,
)


def _days_since(moment: datetime) -> int:
    return max(0, (datetime.now(UTC) - moment).days)


def actuality_status(days: int) -> str:
    if days <= ACTIVE_DAYS:
        return "active"
    if days <= 90:
        return "recent"
    return "stale"


def card(row: CandidateIndex) -> CandidateCard:
    days = _days_since(row.last_active_at)
    return CandidateCard(
        user_id=row.user_id,
        full_name=row.full_name,
        headline=row.headline,
        city=row.city,
        relocation_ready=row.relocation_ready,
        job_search_status=row.job_search_status,
        roles=row.roles,
        category=Category(
            specialization=row.specialization,
            grade=row.grade,
            grade_status=row.grade_status,
            industry=row.industry,
            verified_percent=row.verified_percent,
            test_title=row.test_title,
        ),
        skills=row.skills_display,
        experience_months=row.experience_months,
        work_formats=row.work_formats,
        salary_from=row.salary_from,
        salary_currency=row.salary_currency,
        fsp_count=row.fsp_count,
        fsp_achievements=row.fsp_achievements,
        actuality=Actuality(
            status=actuality_status(days),
            last_active_at=row.last_active_at,
            days_since_active=days,
            **{
                k: v
                for k, v in (row.activity or {}).items()
                if k in Actuality.model_fields
            },
        ),
        has_photo=row.has_photo,
    )


class TalentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Поиск по банку кандидатов ------------------------------------------

    async def search(
        self,
        *,
        specialization: str | None,
        grades: list[str],
        grade_status: str | None,
        skills: list[str],
        skills_mode: str = "all",
        has_fsp: bool | None,
        industry: str | None,
        city: str | None,
        work_format: str | None,
        q: str | None,
        experience_min_months: int | None = None,
        experience_max_months: int | None = None,
        salary_max: int | None = None,
        active_only: bool,
        include_not_looking: bool,
        sort: str,
        limit: int,
        offset: int,
    ) -> SearchPage:
        query: Select[Any] = select(CandidateIndex)
        conditions = []
        keys = [s.lower() for s in skills]
        if specialization:
            conditions.append(
                or_(
                    CandidateIndex.roles.contains([specialization]),
                    CandidateIndex.specialization == specialization,
                )
            )
        if grades:
            conditions.append(CandidateIndex.grade.in_(grades))
        if grade_status:
            conditions.append(CandidateIndex.grade_status == grade_status)
        if keys:
            conditions.append(
                CandidateIndex.skills.contains(keys)
                if skills_mode == "all"
                else CandidateIndex.skills.overlap(keys)
            )
        if has_fsp is not None:
            conditions.append(
                CandidateIndex.fsp_count > 0
                if has_fsp
                else CandidateIndex.fsp_count == 0
            )
        if industry:
            conditions.append(CandidateIndex.industry == industry)
        if city:
            conditions.append(
                or_(
                    func.lower(CandidateIndex.city) == city.lower(),
                    CandidateIndex.relocation_ready,
                    CandidateIndex.work_formats.contains(["remote"]),
                )
            )
        if work_format:
            conditions.append(CandidateIndex.work_formats.contains([work_format]))
        if experience_min_months is not None:
            conditions.append(CandidateIndex.experience_months >= experience_min_months)
        if experience_max_months is not None:
            conditions.append(CandidateIndex.experience_months <= experience_max_months)
        if salary_max is not None:
            # Скрытые ожидания не отсекаем: их можно обсудить.
            conditions.append(
                or_(
                    CandidateIndex.salary_from.is_(None),
                    CandidateIndex.salary_from <= salary_max,
                )
            )
        if active_only:
            conditions.append(
                CandidateIndex.last_active_at
                >= func.now() - func.make_interval(0, 0, 0, ACTIVE_DAYS)
            )
        if not include_not_looking:
            conditions.append(CandidateIndex.job_search_status != "not_looking")
        ts_query = None
        if q:
            ts_query = func.websearch_to_tsquery("russian", q).op("||")(
                func.websearch_to_tsquery("simple", q)
            )
            conditions.append(CandidateIndex.search_vector.op("@@")(ts_query))
        if conditions:
            query = query.where(and_(*conditions))

        total = (
            await self.session.scalar(
                select(func.count()).select_from(query.subquery())
            )
            or 0
        )
        filtered = query.subquery()
        facet_rows = await self.session.execute(
            select(
                filtered.c.specialization,
                filtered.c.grade,
                filtered.c.grade_status,
                func.count(),
            ).group_by(
                filtered.c.specialization, filtered.c.grade, filtered.c.grade_status
            )
        )
        facets = {(r[0], r[1], r[2]): r[3] for r in facet_rows}

        if sort == "skills" and keys:
            # Сколько из запрошенных навыков есть у кандидата.
            overlap = text(
                "cardinality(ARRAY(SELECT unnest(candidate_index.skills) "
                "INTERSECT SELECT unnest(CAST(:sort_skills AS varchar[])))) DESC"
            ).bindparams(sort_skills=keys)
            order = [overlap, CandidateIndex.last_active_at.desc()]
        else:
            order = {
                "actuality": [CandidateIndex.last_active_at.desc()],
                "experience": [CandidateIndex.experience_months.desc()],
                "fsp": [
                    CandidateIndex.fsp_count.desc(),
                    CandidateIndex.last_active_at.desc(),
                ],
            }.get(sort, [])
        if not order:
            # Релевантность запросу, затем подтверждённые и актуальные.
            if ts_query is not None:
                order.append(
                    func.ts_rank(CandidateIndex.search_vector, ts_query).desc()
                )
            order += [
                (CandidateIndex.grade_status == "confirmed").desc(),
                CandidateIndex.last_active_at.desc(),
            ]
        rows = await self.session.scalars(
            query.order_by(*order).limit(limit).offset(offset)
        )
        return SearchPage(
            total=total,
            items=[card(row) for row in rows],
            categories=[
                CategoryCount(
                    specialization=k[0], grade=k[1], grade_status=k[2], count=c
                )
                for k, c in sorted(facets.items(), key=lambda item: -item[1])
            ],
        )

    # --- Подборка по потребности ---------------------------------------------------

    async def _keyword_hits(
        self, ids: list[uuid.UUID], keywords: list[str]
    ) -> dict[uuid.UUID, list[str]]:
        """Какие ключевые слова потребности встречаются в опыте кандидата
        (с учётом морфологии)."""
        if not ids or not keywords:
            return {}
        rows = await self.session.execute(
            text(
                "SELECT c.user_id, k FROM candidate_index c, "
                "unnest(CAST(:keywords AS text[])) AS k "
                "WHERE c.user_id = ANY(CAST(:ids AS uuid[])) AND c.search_vector @@ "
                "(plainto_tsquery('russian', k) || plainto_tsquery('simple', k))"
            ),
            {"keywords": keywords, "ids": ids},
        )
        hits: dict[uuid.UUID, list[str]] = defaultdict(list)
        for user_id, keyword in rows:
            hits[user_id].append(keyword)
        # В порядке ключевых слов потребности.
        return {
            user_id: [k for k in keywords if k in found]
            for user_id, found in hits.items()
        }

    async def _rows(self, ids: list[uuid.UUID]) -> list[CandidateIndex]:
        if not ids:
            return []
        return list(
            await self.session.scalars(
                select(CandidateIndex).where(CandidateIndex.user_id.in_(ids))
            )
        )

    async def match(self, criteria: MatchCriteria) -> MatchResult:
        """Подборка: отбор кандидатов, жёсткие фильтры, ранжирование,
        категории и подсказки, что ослабить."""
        required_keys = [s.lower() for s in criteria.required_skills]
        stack_keys = (
            set(required_keys)
            | {
                r.lower()
                for s in criteria.required_skills + criteria.optional_skills
                for r in related_skills(s)
            }
            | {s.lower() for s in criteria.optional_skills}
        )
        pool_query = select(CandidateIndex).where(
            CandidateIndex.job_search_status != "not_looking",
            or_(
                CandidateIndex.roles.contains([criteria.specialization]),
                CandidateIndex.specialization == criteria.specialization,
                CandidateIndex.skills.overlap(list(stack_keys))
                if stack_keys
                else False,
            ),
        )
        pool = list(await self.session.scalars(pool_query))

        keywords = extract_keywords(criteria.title, criteria.team_description)
        keyword_hits = await self._keyword_hits([r.user_id for r in pool], keywords)
        liked = Preference.from_rows(await self._rows(criteria.liked_ids))
        disliked = Preference.from_rows(await self._rows(criteria.disliked_ids))
        liked_ids, disliked_ids = set(criteria.liked_ids), set(criteria.disliked_ids)

        excluded: Counter[str] = Counter()
        blockers: Counter[str] = Counter()
        skill_blockers: Counter[str] = Counter()
        kept = []
        for row in pool:
            contact = criteria.contacted.get(row.user_id)
            if row.user_id in disliked_ids:
                excluded["disliked"] += 1
                continue
            if contact and contact.endswith(":declined"):
                excluded["declined"] += 1
                continue
            if contact == "application:rejected":
                excluded["rejected"] += 1
                continue
            if contact and criteria.hide_contacted:
                excluded["contacted"] += 1
                continue
            required = match_skills(criteria.required_skills, row)
            codes = hard_filters(row, criteria, required)
            if codes:
                excluded.update(codes)
                # Единственное препятствие — по нему видно, что ослабить.
                if len(codes) == 1:
                    blockers[codes[0]] += 1
                    blocking = required.missing + [r.required for r in required.related]
                    if codes == ["missing_required_skills"] and len(blocking) == 1:
                        skill_blockers[blocking[0]] += 1
                continue
            coverage = required_coverage(required, len(criteria.required_skills))
            if coverage < MIN_REQUIRED_COVERAGE and row.user_id not in liked_ids:
                excluded["insufficient_skills"] += 1
                continue
            evaluation = evaluate(
                row,
                criteria,
                required=required,
                keywords=keywords,
                matched_keywords=keyword_hits.get(row.user_id, []),
                liked=liked,
                disliked=disliked,
            )
            if (
                evaluation.score < settings.match_min_score
                and row.user_id not in liked_ids
            ):
                excluded["low_score"] += 1
                continue
            kept.append((evaluation, row, contact))

        kept.sort(
            key=lambda item: (
                -item[0].score,
                item[1].grade_status != "confirmed",
                -item[1].last_active_at.timestamp(),
            )
        )
        page = kept[criteria.offset : criteria.offset + criteria.limit]
        return MatchResult(
            total=len(kept),
            categories=self._categories(kept, criteria),
            candidates=[
                MatchedCandidate(
                    score=evaluation.score,
                    fit=fit_label(evaluation.score),
                    reasons=evaluation.reasons,
                    warnings=evaluation.warnings,
                    breakdown=evaluation.breakdown,
                    matched_skills=evaluation.required.matched,
                    related_skills=evaluation.required.related,
                    missing_skills=evaluation.required.missing,
                    contact_status=contact,
                    feedback=(
                        "like"
                        if row.user_id in liked_ids
                        else "dislike"
                        if row.user_id in disliked_ids
                        else None
                    ),
                    candidate=card(row),
                )
                for evaluation, row, contact in page
            ],
            excluded=dict(excluded),
            suggestions=self._suggestions(blockers, skill_blockers, criteria),
            keywords=keywords,
        )

    @staticmethod
    def _categories(kept: list[Any], criteria: MatchCriteria) -> list[CategoryCount]:
        groups: dict[tuple[Any, Any, str], list[int]] = defaultdict(list)
        for evaluation, row, _ in kept:
            specialization = (
                criteria.specialization
                if criteria.specialization in row.roles
                else row.specialization or (row.roles[0] if row.roles else None)
            )
            groups[(specialization, row.grade, row.grade_status)].append(
                evaluation.score
            )
        ordered = sorted(
            groups.items(), key=lambda item: (-max(item[1]), -len(item[1]))
        )
        return [
            CategoryCount(
                specialization=spec,
                grade=grade,
                grade_status=status,
                count=len(scores),
                best_score=max(scores),
                avg_score=round(sum(scores) / len(scores)),
                hint=category_hint(spec, grade, criteria)
                + (", грейд подтверждён" if status == "confirmed" else ""),
            )
            for (spec, grade, status), scores in ordered
        ]

    @staticmethod
    def _suggestions(
        blockers: Counter[str], skill_blockers: Counter[str], criteria: MatchCriteria
    ) -> list[Suggestion]:
        suggestions = [
            Suggestion(
                text=f"Сделайте навык «{skill}» желательным, а не обязательным",
                extra_candidates=count,
            )
            for skill, count in skill_blockers.items()
        ]
        for code, count in blockers.items():
            if code == "missing_required_skills" and skill_blockers:
                continue
            suggestions.append(
                Suggestion(
                    text=exclusion_suggestion(code, criteria), extra_candidates=count
                )
            )
        return sorted(suggestions, key=lambda s: -s.extra_candidates)[:5]

    # --- Похожие кандидаты ---------------------------------------------------------

    async def similar(self, user_id: uuid.UUID, limit: int) -> list[SimilarCandidate]:
        """Кандидаты, похожие на выбранного: стек, специализация, грейд."""
        base = await self.session.get(CandidateIndex, user_id)
        if base is None:
            return []
        pool = await self.session.scalars(
            select(CandidateIndex).where(
                CandidateIndex.user_id != user_id,
                CandidateIndex.job_search_status != "not_looking",
                or_(
                    CandidateIndex.skills.overlap(base.skills or [""]),
                    CandidateIndex.roles.overlap(base.roles or [""]),
                ),
            )
        )
        base_skills = set(base.skills)
        results = []
        for row in pool:
            shared = base_skills & set(row.skills)
            union = base_skills | set(row.skills)
            jaccard = len(shared) / len(union) if union else 0.0
            same_role = bool(set(base.roles) & set(row.roles))
            grade_close = 0.0
            if base.grade and row.grade:
                distance = abs(
                    GRADE_ORDER[Grade(base.grade)] - GRADE_ORDER[Grade(row.grade)]
                )
                grade_close = max(0.0, 1 - distance / 2)
            similarity = 0.6 * jaccard + 0.25 * same_role + 0.15 * grade_close
            if similarity < 0.2:
                continue
            names = [
                s["name"] for s in row.skills_display if s["name"].lower() in shared
            ]
            results.append(
                SimilarCandidate(
                    similarity=round(similarity * 100),
                    shared_skills=names,
                    candidate=card(row),
                )
            )
        results.sort(key=lambda r: -r.similarity)
        return results[:limit]
