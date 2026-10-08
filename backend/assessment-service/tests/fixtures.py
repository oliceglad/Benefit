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
    ],
}
