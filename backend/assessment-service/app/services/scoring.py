"""Проверка ответов и итог тестирования."""

from typing import Any

from benefit_common.dictionaries import Grade, next_grade
from benefit_common.errors import AppError

from app.core.config import settings
from app.models import AssessmentTask, Outcome, TaskKind


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _invalid(message: str) -> AppError:
    return AppError(message, code="invalid_answer", status_code=422)


def validate_answer(task: AssessmentTask, answer: Any) -> Any:
    """Приводит ответ к каноническому виду; ``None`` — задача пропущена."""
    if answer is None:
        return None
    option_ids = {option["id"] for option in task.options}
    match task.kind:
        case TaskKind.SINGLE_CHOICE:
            value = (
                answer[0] if isinstance(answer, list) and len(answer) == 1 else answer
            )
            if not isinstance(value, str) or value not in option_ids:
                raise _invalid("Выберите один из вариантов ответа")
            return [value]
        case TaskKind.MULTIPLE_CHOICE:
            if not isinstance(answer, list) or not answer:
                raise _invalid("Выберите хотя бы один вариант ответа")
            if not set(answer) <= option_ids:
                raise _invalid("Неизвестный вариант ответа")
            return sorted(set(answer))
        case TaskKind.TEXT:
            if not isinstance(answer, str) or not answer.strip() or len(answer) > 1000:
                raise _invalid("Введите ответ текстом (до 1000 символов)")
            return answer.strip()
    raise _invalid("Неизвестный тип задачи")


def score(task: AssessmentTask, answer: Any) -> tuple[float, bool]:
    """Доля баллов (0..1) и признак полностью верного ответа.

    Множественный выбор оценивается частично: за каждый лишний вариант
    снимается столько же, сколько даёт верный, но не ниже нуля.
    """
    if answer is None:
        return 0.0, False
    correct = set(task.correct)
    match task.kind:
        case TaskKind.SINGLE_CHOICE:
            ok = answer[0] in correct
            return float(ok), ok
        case TaskKind.MULTIPLE_CHOICE:
            chosen = set(answer)
            hits, misses = len(chosen & correct), len(chosen - correct)
            fraction = max(0.0, (hits - misses) / len(correct))
            return fraction, chosen == correct
        case TaskKind.TEXT:
            ok = _normalize_text(answer) in {_normalize_text(c) for c in correct}
            return float(ok), ok
    return 0.0, False


def evaluate(percent: float, target: Grade) -> tuple[Outcome, Grade | None]:
    """Итог по проценту набранных баллов.

    Ниже порога грейд не подтверждается (а не понижается): работодатель
    увидит заявленный грейд с пометкой «не подтверждён».
    """
    if percent >= settings.exceed_percent and target != Grade.LEAD:
        return Outcome.EXCEEDED, next_grade(target)
    if percent >= settings.pass_percent:
        return Outcome.CONFIRMED, target
    return Outcome.NOT_CONFIRMED, None


def evaluate_level(
    percent: float, levels: list[dict[str, Any]]
) -> tuple[Outcome, dict[str, Any] | None]:
    """Уровень навыка — самая высокая ступень шкалы, порог которой набран.

    Ниже первой ступени уровень не подтверждается.
    """
    reached = [level for level in levels if percent >= level["min_percent"]]
    if not reached:
        return Outcome.NOT_CONFIRMED, None
    return Outcome.CONFIRMED, reached[-1]
