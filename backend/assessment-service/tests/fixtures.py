"""Синтетический пакет тестов для автотестов (без реального контента)."""

from typing import Any


def _task(index: int, skill: str, kind: str) -> dict[str, Any]:
    options = [{"id": c, "text": f"Вариант {c}"} for c in "abcd"]
    task: dict[str, Any] = {
        "key": f"task-{index}",
        "kind": kind,
        "prompt": f"Задача {index} ({skill})",
        "points": 5 + 5 * (index % 3),
        "time_limit_seconds": 60,
        "skills": [skill],
    }
    if kind == "single_choice":
        task |= {"options": options, "correct": ["b"]}
    elif kind == "multiple_choice":
        task |= {"options": options, "correct": ["a", "c"]}
    else:
        task |= {"correct": ["Ответ"]}
    return task


def _test(
    slug: str, specialization: str, grade: str, skills: list[str], size: int
) -> dict[str, Any]:
    kinds = ["single_choice", "multiple_choice", "text"]
    return {
        "slug": slug,
        "title": f"Тест {slug}",
        "description": "Синтетический тест",
        "specialization": specialization,
        "grade": grade,
        "time_limit_seconds": 1200,
        "tasks_per_attempt": 8,
        "tasks": [
            _task(i, skills[i % len(skills)], kinds[i % len(kinds)])
            for i in range(1, size + 1)
        ],
    }


# Шкала теста на навык: уровень — по проценту набранных баллов.
LEVELS = [
    {"id": "a2", "title": "A2 — Elementary", "min_percent": 30},
    {"id": "b1", "title": "B1 — Intermediate", "min_percent": 50},
    {"id": "b2", "title": "B2 — Upper-Intermediate", "min_percent": 70},
    {"id": "c1", "title": "C1 — Advanced", "min_percent": 85},
]


def _skill_test(slug: str, skill: str, size: int) -> dict[str, Any]:
    test = _test(slug, "backend", "middle", [skill], size)
    del test["specialization"], test["grade"]
    # Все задачи одной стоимости: процент = доля верных ответов.
    for task in test["tasks"]:
        task |= {"kind": "single_choice", "points": 10}
        task |= {
            "options": [{"id": c, "text": f"Вариант {c}"} for c in "abcd"],
            "correct": ["b"],
        }
    return test | {
        "kind": "skill",
        "skill": skill,
        "levels": LEVELS,
        "tasks_per_attempt": 10,
    }


SAMPLE_PACK: dict[str, Any] = {
    "format_version": 1,
    "tests": [
        _test(
            "backend-middle",
            "backend",
            "middle",
            ["Python", "PostgreSQL", "Docker"],
            12,
        ),
        _test("qa-junior", "qa_automation", "junior", ["Pytest", "SQL"], 10),
        _skill_test("english", "English", 12),
    ],
}
