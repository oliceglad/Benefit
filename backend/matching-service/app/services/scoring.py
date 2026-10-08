"""Оценка соответствия кандидата потребности работодателя.

Подбор состоит из двух этапов:

1. **Жёсткие фильтры** (``hard_filters``) — требования, без которых кандидат
   не подходит: обязательные навыки (в строгом режиме), допустимый грейд,
   подтверждение грейда, стаж, бюджет, формат и город. Кандидат либо
   проходит, либо исключается с кодом причины — по этим кодам строятся
   подсказки «что ослабить, чтобы найти больше».
2. **Ранжирование** (``evaluate``) — оценка 0–100 из прозрачных компонентов:

   ============================  ======
   обязательный стек              35
   специализация                  15
   грейд                          15
   подтверждение грейда тестом    10
   близость опыта к задачам        8
   активность и надёжность         7
   желательный стек                5
   достижения ФСП                  3
   отрасль                         2
   ============================  ======

   плюс персонализация по отметкам работодателя (до +8 / −5) и штрафы
   (ожидания выше бюджета, давно неактивен, формат, стаж не по грейду).

Навык засчитывается не бинарно: полное совпадение даёт 0.7 доли и до 0.3
за подтверждение (уровень владения, месяцы в стеке реальных мест работы,
свежесть); близкая технология (RabbitMQ вместо Kafka) — 0.4.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from benefit_common.dictionaries import (
    GRADE_ORDER,
    GRADE_TITLES,
    INDUSTRY_TITLES,
    ROLE_TITLES,
    WORK_FORMAT_TITLES,
    Grade,
)
from benefit_common.skills import find_skill, related_skills

from app.models import CandidateIndex
from app.schemas.talent import MatchCriteria, RelatedSkill, ScorePart

ACTIVE_DAYS = 30
RECENT_DAYS = 90
# Навык считается «свежим», если использовался за последние 2 года.
FRESH_MONTHS = 24

LEVEL_BONUS = {"expert": 0.15, "advanced": 0.12, "intermediate": 0.08, "basic": 0.03}

# Ожидаемый стаж для грейда (месяцы): ниже — подозрительно, выше — нормально.
GRADE_MIN_EXPERIENCE = {
    Grade.INTERN: 0,
    Grade.JUNIOR: 0,
    Grade.MIDDLE: 18,
    Grade.SENIOR: 48,
    Grade.LEAD: 60,
}

EXCLUSION_TITLES = {
    "missing_required_skills": "нет обязательных навыков",
    "grade_out_of_range": "грейд вне допустимого диапазона",
    "unconfirmed_grade": "грейд не подтверждён тестированием",
    "experience_too_low": "недостаточный стаж",
    "over_budget": "ожидания выше бюджета",
    "format_mismatch": "другой формат работы",
    "city_mismatch": "другой город без готовности к переезду",
    "disliked": "отмечен как неподходящий",
    "declined": "уже отказался от вашего приглашения",
    "rejected": "вы уже отклонили его отклик",
    "contacted": "уже был контакт",
    "insufficient_skills": "закрывает меньше половины обязательного стека",
    "low_score": "низкое соответствие",
}

STOPWORDS = {
    "команда",
    "команде",
    "команду",
    "команды",
    "который",
    "которые",
    "которая",
    "также",
    "работа",
    "работы",
    "работать",
    "нужен",
    "нужна",
    "нужны",
    "ищем",
    "наша",
    "наши",
    "наше",
    "наших",
    "нашей",
    "наш",
    "человек",
    "людей",
    "занимается",
    "занимаемся",
    "делаем",
    "делает",
    "компании",
    "компания",
    "очень",
    "более",
    "этого",
    "этом",
    "этой",
    "чтобы",
    "будет",
    "будете",
    "можно",
    "сейчас",
    "специалист",
    "разработчик",
    "разработчика",
    "with",
    "and",
    "the",
    "for",
    "team",
}


def now() -> datetime:
    return datetime.now(UTC)


def extract_keywords(*texts: str | None, limit: int = 12) -> list[str]:
    """Ключевые слова из описания потребности (без навыков и стоп-слов).

    Похожие формы одного слова (по первым 5 буквам) берутся один раз:
    морфологию дальше учитывает полнотекстовый поиск PostgreSQL.
    """
    words: list[str] = []
    stems: set[str] = set()
    for text in texts:
        for word in re.findall(r"[а-яёa-z][а-яёa-z0-9]{3,}", (text or "").lower()):
            if word in STOPWORDS or find_skill(word):
                continue
            stem = word[:5]
            if stem not in stems:
                stems.add(stem)
                words.append(word)
    return words[:limit]


@dataclass
class SkillMatch:
    matched: list[str] = field(default_factory=list)
    related: list[RelatedSkill] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    credit: float = 0.0
    details: list[str] = field(default_factory=list)


def _months_since(last_used: str) -> int:
    year, month = (int(p) for p in last_used.split("-"))
    today = date.today()
    return (today.year - year) * 12 + today.month - month


def skill_credit(
    skill: str, row: CandidateIndex
) -> tuple[float, str | None, str | None]:
    """Доля зачёта навыка, близкий навык (если зачтён он) и пояснение."""
    key = skill.lower()
    if key in row.skills:
        credit = 0.7
        level = next(
            (s.get("level") for s in row.skills_display if s["name"].lower() == key),
            None,
        )
        credit += LEVEL_BONUS.get(level or "", 0.0)
        evidence = (row.skill_experience or {}).get(key)
        detail = None
        if evidence:
            months = evidence["months"]
            credit += 0.15 if months >= 24 else 0.1 if months >= 12 else 0.05
            fresh = _months_since(evidence["last_used"]) <= FRESH_MONTHS
            if not fresh:
                credit -= 0.1
            years = months / 12
            detail = f"{skill} — {years:.1f} г. в работе".replace(".0 г.", " г.") + (
                "" if fresh else ", давно не использовал"
            )
        return min(1.0, credit), None, detail
    for related in sorted(related_skills(skill)):
        if related.lower() in row.skills:
            return 0.4, related, None
    return 0.0, None, None


def match_skills(skills: list[str], row: CandidateIndex) -> SkillMatch:
    result = SkillMatch()
    if not skills:
        return result
    total = 0.0
    for skill in skills:
        credit, related, detail = skill_credit(skill, row)
        total += credit
        if related:
            result.related.append(RelatedSkill(required=skill, has=related))
        elif credit:
            result.matched.append(skill)
            if detail:
                result.details.append(detail)
        else:
            result.missing.append(skill)
    result.credit = total / len(skills)
    return result


def days_inactive(row: CandidateIndex) -> int:
    return max(0, (now() - row.last_active_at).days)


def grade_diff(row: CandidateIndex, criteria: MatchCriteria) -> int | None:
    if not row.grade:
        return None
    return GRADE_ORDER[Grade(row.grade)] - GRADE_ORDER[criteria.grade]


def hard_filters(
    row: CandidateIndex, criteria: MatchCriteria, required: SkillMatch
) -> list[str]:
    """Коды требований, которым кандидат не удовлетворяет."""
    reasons = []
    # В строгом режиме близкая технология не заменяет обязательную.
    if criteria.strict_skills and (required.missing or required.related):
        reasons.append("missing_required_skills")
    diff = grade_diff(row, criteria)
    if diff is None or abs(diff) > criteria.grade_tolerance:
        reasons.append("grade_out_of_range")
    if criteria.require_confirmed_grade and row.grade_status != "confirmed":
        reasons.append("unconfirmed_grade")
    if (
        criteria.min_experience_months
        and row.experience_months < criteria.min_experience_months
    ):
        reasons.append("experience_too_low")
    if (
        criteria.hard_budget
        and criteria.salary_to
        and row.salary_from
        and row.salary_from > criteria.salary_to
    ):
        reasons.append("over_budget")
    if (
        criteria.strict_format
        and criteria.work_formats
        and row.work_formats
        and not set(criteria.work_formats) & set(row.work_formats)
    ):
        reasons.append("format_mismatch")
    office_only = criteria.work_formats and set(criteria.work_formats) == {"office"}
    if (
        office_only
        and criteria.city
        and row.city
        and row.city.lower() != criteria.city.lower()
        and not row.relocation_ready
    ):
        reasons.append("city_mismatch")
    return reasons


# Минимальная доля обязательного стека (точные + близкие навыки).
MIN_REQUIRED_COVERAGE = 0.5


def required_coverage(required: SkillMatch, total: int) -> float:
    if not total:
        return 1.0
    return (len(required.matched) + len(required.related)) / total


@dataclass
class Preference:
    """Профиль предпочтений из отметок работодателя: вес навыка — доля
    отмеченных кандидатов, у которых он есть."""

    weights: dict[str, float]

    @classmethod
    def from_rows(cls, rows: list[CandidateIndex]) -> "Preference | None":
        if not rows:
            return None
        counts = Counter(skill for row in rows for skill in set(row.skills))
        return cls({skill: count / len(rows) for skill, count in counts.items()})

    def similarity(self, row: CandidateIndex) -> tuple[float, list[str]]:
        total = sum(self.weights.values())
        shared = [s for s in row.skills if s in self.weights]
        if not total:
            return 0.0, []
        top = sorted(shared, key=lambda s: -self.weights[s])[:3]
        return sum(self.weights[s] for s in shared) / total, top


@dataclass
class Evaluation:
    score: int
    breakdown: list[ScorePart]
    reasons: list[str]
    warnings: list[str]
    required: SkillMatch
    optional: SkillMatch


def _display(skill_key: str, row: CandidateIndex) -> str:
    return next(
        (s["name"] for s in row.skills_display if s["name"].lower() == skill_key),
        skill_key,
    )


def evaluate(
    row: CandidateIndex,
    criteria: MatchCriteria,
    *,
    required: SkillMatch,
    keywords: list[str],
    matched_keywords: list[str],
    liked: Preference | None = None,
    disliked: Preference | None = None,
) -> Evaluation:
    reasons: list[str] = []
    warnings: list[str] = []
    parts: list[ScorePart] = []

    def part(component: str, title: str, points: float, maximum: float) -> None:
        parts.append(
            ScorePart(
                component=component,
                title=title,
                points=round(points, 1),
                max_points=maximum,
            )
        )

    # Обязательный стек.
    if criteria.required_skills:
        part("required_skills", "Обязательный стек", 35 * required.credit, 35)
        if required.matched:
            reasons.append(
                f"Стек: {', '.join(required.matched)} "
                f"({len(required.matched)} из {len(criteria.required_skills)})"
            )
        if required.details:
            reasons.append("Опыт со стеком: " + "; ".join(required.details[:3]))
        for item in required.related:
            reasons.append(
                f"Нет {item.required}, но есть {item.has} (близкая технология)"
            )
        if required.missing:
            warnings.append(f"Нет в стеке: {', '.join(required.missing)}")
    else:
        part("required_skills", "Обязательный стек", 35, 35)

    # Желательный стек.
    optional = match_skills(criteria.optional_skills, row)
    if criteria.optional_skills:
        part("optional_skills", "Желательный стек", 5 * optional.credit, 5)
        extra = optional.matched + [
            f"{r.has} (вместо {r.required})" for r in optional.related
        ]
        if extra:
            reasons.append(f"Дополнительно: {', '.join(extra)}")

    # Специализация.
    if criteria.specialization in row.roles:
        part("specialization", "Специализация", 15, 15)
        reasons.insert(0, f"Специализация: {ROLE_TITLES[criteria.specialization]}")
    else:
        part("specialization", "Специализация", 0, 15)
        warnings.append("Другая основная специализация, совпадает по стеку")

    # Грейд и его согласованность со стажем.
    diff = grade_diff(row, criteria)
    grade_points = {0: 15, 1: 11, -1: 5}.get(diff, 0) if diff is not None else 0
    part("grade", "Грейд", grade_points, 15)
    if row.grade:
        title = GRADE_TITLES[Grade(row.grade)]
        if diff == 0:
            reasons.append(f"Грейд {title} совпадает с требуемым")
        elif diff == 1:
            reasons.append(f"Грейд {title} — на ступень выше требуемого")
        elif diff is not None and diff < 0:
            warnings.append(f"Грейд {title} ниже требуемого")
        else:
            warnings.append(f"Грейд {title} заметно выше требуемого")
        expected = GRADE_MIN_EXPERIENCE[Grade(row.grade)]
        if row.experience_months < expected:
            warnings.append(
                f"Стаж {row.experience_months // 12} г. маловат для грейда {title}"
            )
    if row.grade_status == "confirmed":
        part("confirmation", "Подтверждение грейда", 10, 10)
        detail = f" ({row.verified_percent:g}%)" if row.verified_percent else ""
        reasons.append(f"Грейд подтверждён тестированием{detail}")
    else:
        part("confirmation", "Подтверждение грейда", 0, 10)
        warnings.append("Грейд заявлен, но не подтверждён тестированием")

    # Близость опыта к задачам команды.
    if keywords:
        coverage = min(1.0, 2 * len(matched_keywords) / len(keywords))
        part("relevance", "Близость опыта к задачам", 8 * coverage, 8)
        if matched_keywords:
            reasons.append(
                "Опыт близок к задачам команды: " + ", ".join(matched_keywords[:5])
            )

    # Активность и надёжность.
    days = days_inactive(row)
    activity = row.activity or {}
    reliability = 3 if days <= ACTIVE_DAYS else 1 if days <= RECENT_DAYS else 0
    if days <= ACTIVE_DAYS:
        reasons.append(f"Профиль актуален: активность {days} дн. назад")
    if activity.get("tasks_passed"):
        reliability += 2
        reasons.append(f"Принятых заданий работодателей: {activity['tasks_passed']}")
    if activity.get("employer_tests_completed"):
        reliability += 1
    if row.experience_months:
        reliability += 1
        years, months = divmod(row.experience_months, 12)
        reasons.append(f"Опыт работы: {years} г. {months} мес.".replace(" 0 мес.", ""))
    part("reliability", "Активность и надёжность", reliability, 7)

    # Достижения ФСП.
    if row.fsp_count:
        strong = any(
            a.get("level") in ("federal", "international")
            and a.get("result") in ("winner", "prize")
            for a in row.fsp_achievements
        )
        part("fsp", "Достижения ФСП", 3 if strong else 1.5, 3)
        best = row.fsp_achievements[0] if row.fsp_achievements else {}
        place = f", {best['place']} место" if best.get("place") else ""
        reasons.append(
            f"Достижения ФСП: {row.fsp_count}"
            + (
                f" (например, «{best.get('event')}»{place})"
                if best.get("event")
                else ""
            )
        )
    else:
        part("fsp", "Достижения ФСП", 0, 3)

    # Отрасль.
    if criteria.industry and row.industry == criteria.industry:
        part("industry", "Отрасль", 2, 2)
        reasons.append(f"Опыт в отрасли: {INDUSTRY_TITLES[criteria.industry]}")
    elif criteria.industry:
        part("industry", "Отрасль", 0, 2)

    # Персонализация по отметкам работодателя.
    personal = 0.0
    if liked:
        similarity, shared = liked.similarity(row)
        personal += 8 * similarity
        if similarity >= 0.4 and shared:
            names = ", ".join(_display(s, row) for s in shared)
            reasons.append(f"Похож на отмеченных вами кандидатов: {names}")
    if disliked:
        similarity, _ = disliked.similarity(row)
        personal -= 5 * similarity
    if liked or disliked:
        part("personalization", "Похожесть на отмеченных вами", personal, 8)

    # Штрафы.
    penalty = 0.0
    if days > RECENT_DAYS:
        penalty += 5
        warnings.append(f"Давно не обновлял профиль ({days} дн.)")
    if criteria.salary_to and row.salary_from:
        if row.salary_from > criteria.salary_to:
            penalty += 10
            warnings.append(
                f"Ожидания выше бюджета: от {row.salary_from:,}".replace(",", " ")
            )
        else:
            reasons.append("Зарплатные ожидания в рамках бюджета")
    if criteria.work_formats and row.work_formats:
        common = set(criteria.work_formats) & set(row.work_formats)
        if common:
            reasons.append(
                "Формат работы: "
                + ", ".join(WORK_FORMAT_TITLES[f] for f in sorted(common))
            )
        else:
            penalty += 3
            warnings.append("Предпочитает другой формат работы")
    if criteria.city and row.city and row.city.lower() != criteria.city.lower():
        if row.relocation_ready:
            reasons.append(f"Готов к переезду (сейчас — {row.city})")
        elif "remote" not in criteria.work_formats:
            penalty += 3
            warnings.append(f"Живёт в другом городе ({row.city})")
    if row.job_search_status == "open":
        penalty += 2
        warnings.append("Не ищет активно, но рассматривает предложения")
    if penalty:
        part("penalties", "Штрафы", -penalty, 0)

    score = sum(p.points for p in parts)
    return Evaluation(
        score=max(0, min(100, round(score))),
        breakdown=parts,
        reasons=reasons,
        warnings=warnings,
        required=required,
        optional=optional,
    )


def fit_label(score: int) -> str:
    if score >= 80:
        return "excellent"
    if score >= 65:
        return "good"
    return "partial"


def category_hint(
    specialization: str | None, grade: str | None, criteria: MatchCriteria
) -> str:
    if specialization != criteria.specialization:
        return "Смежная специализация: совпадение по стеку"
    if grade is None:
        return "Грейд не указан"
    diff = GRADE_ORDER[Grade(grade)] - GRADE_ORDER[criteria.grade]
    if diff == 0:
        return "Точное совпадение по специализации и грейду"
    if diff > 0:
        return "Грейд выше требуемого: сильнее, но, вероятно, дороже"
    return "Грейд ниже требуемого: можно вырастить в команде"


def exclusion_suggestion(code: str, criteria: MatchCriteria) -> str:
    return {
        "unconfirmed_grade": "Снимите требование подтверждённого грейда",
        "grade_out_of_range": "Расширьте допустимый диапазон грейда",
        "experience_too_low": "Снизьте требование к стажу",
        "over_budget": "Сделайте бюджет мягким ограничением или увеличьте его",
        "format_mismatch": "Рассмотрите другие форматы работы",
        "city_mismatch": "Рассмотрите удалённый или гибридный формат",
        "missing_required_skills": "Сделайте часть обязательных навыков желательными",
    }.get(code, f"Ослабьте требование: {EXCLUSION_TITLES.get(code, code)}")
