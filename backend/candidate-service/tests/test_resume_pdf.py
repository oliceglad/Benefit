import pytest
from httpx import AsyncClient

from app.services.pdf_import import HeuristicResumeParser
from tests.conftest import API, FULL_PROFILE, User, published_profile

weasyprint = pytest.importorskip(
    "weasyprint", reason="для экспорта PDF нужны системные библиотеки Pango"
)

HH_RESUME = """Петрова Анна Сергеевна
Женщина, 27 лет, родилась 3 марта 1999
+7 (916) 123-45-67
anna.petrova@yandex.ru
Telegram: @anna_qa
Проживает: Москва
Желаемая должность и зарплата
Senior QA Automation Engineer
от 300 000 ₽
Опыт работы — 5 лет 2 месяца
Сентябрь 2021 —
настоящее время
4 года 2 месяца
Тинькофф
Москва, www.tbank.ru
Ведущий инженер по автоматизации тестирования
Строила фреймворк автотестов для мобильного банка.
• Сократила регресс с 3 дней до 4 часов
Стек: Python, Pytest, Playwright, Allure
Сентябрь 2020 — Август 2021
1 год
ООО Лаборатория
Тестировщик
Ручное тестирование веб-приложений.
Образование
Высшее
2021
МГТУ им. Н. Э. Баумана
Информатика и системы управления
Ключевые навыки
Python  Pytest  Selenium  Docker  SQL  Git
Знание языков
Русский — Родной
Английский — C1 — Продвинутый
Дополнительная информация
Обо мне
Люблю находить баги раньше пользователей. Работа в команде и наставничество.
"""


def test_parses_hh_resume() -> None:
    result = HeuristicResumeParser().parse(HH_RESUME)
    draft = result.draft

    assert (draft["last_name"], draft["first_name"], draft["middle_name"]) == (
        "Петрова",
        "Анна",
        "Сергеевна",
    )
    assert draft["birth_date"] == "1999-03-03"
    assert draft["contact_email"] == "anna.petrova@yandex.ru"
    assert draft["phone"] == "+7 (916) 123-45-67"
    assert draft["telegram"] == "anna_qa"
    assert draft["city"] == "Москва"
    assert draft["headline"] == "Senior QA Automation Engineer"
    assert draft["salary_from"] == 300000
    assert draft["grade"] == "senior"
    assert "qa_automation" in draft["roles"]
    names = [s["name"] for s in draft["skills"]]
    assert {"Python", "Pytest", "Selenium", "SQL", "Playwright"} <= set(names)
    assert draft["languages"] == [
        {"language": "Русский", "level": "native"},
        {"language": "Английский", "level": "C1"},
    ]
    first_job, second_job = draft["experience"]
    assert first_job["company"] == "Тинькофф"
    assert first_job["position"] == "Ведущий инженер по автоматизации тестирования"
    assert first_job["start_date"] == "2021-09-01"
    assert first_job["end_date"] is None
    assert first_job["achievements"] == ["Сократила регресс с 3 дней до 4 часов"]
    assert second_job["end_date"] == "2021-08-01"
    assert draft["education"][0]["institution"] == "МГТУ им. Н. Э. Баумана"
    assert "Работа в команде" in draft["soft_skills"]


async def test_export_pdf(client: AsyncClient, candidate: User) -> None:
    await client.patch(f"{API}/me", json=FULL_PROFILE, headers=candidate.headers)

    response = await client.get(f"{API}/me/resume.pdf", headers=candidate.headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


async def test_export_import_round_trip(client: AsyncClient, candidate: User) -> None:
    await client.patch(f"{API}/me", json=FULL_PROFILE, headers=candidate.headers)
    pdf = (await client.get(f"{API}/me/resume.pdf", headers=candidate.headers)).content

    other = User("candidate", "new@mail.ru")
    response = await client.post(
        f"{API}/me/resume/import",
        files={"file": ("resume.pdf", pdf, "application/pdf")},
        headers=other.headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["applied"] is False
    draft = body["draft"]
    assert draft["last_name"] == "Иванов"
    assert draft["middle_name"] == "Иванович"
    assert draft["phone"] == "+79123456789"
    assert draft["telegram"] == "@ivanov_dev"
    assert draft["headline"] == "Python Backend-разработчик"
    assert draft["grade"] == "middle"
    assert draft["salary_from"] == 250000
    assert {"Python", "FastAPI", "PostgreSQL", "Docker"} <= {
        s["name"] for s in draft["skills"]
    }
    assert [job["company"] for job in draft["experience"]] == ["ООО Ромашка", "Яндекс"]
    assert draft["experience"][0]["position"] == "Python-разработчик"
    assert draft["experience"][0]["achievements"] == [
        "Сократил время ответа API в 3 раза"
    ]
    assert draft["experience"][1]["end_date"] == "2022-02-01"
    assert draft["education"][0]["graduation_year"] == 2020
    assert {"language": "Английский", "level": "B2"} in draft["languages"]


async def test_import_apply_fills_only_empty_fields(
    client: AsyncClient, candidate: User
) -> None:
    await client.patch(f"{API}/me", json=FULL_PROFILE, headers=candidate.headers)
    pdf = (await client.get(f"{API}/me/resume.pdf", headers=candidate.headers)).content

    other = User("candidate", "new@mail.ru")
    await client.patch(
        f"{API}/me",
        json={"last_name": "Сидоров", "skills": [{"name": "Go"}]},
        headers=other.headers,
    )
    response = await client.post(
        f"{API}/me/resume/import?apply=true",
        files={"file": ("resume.pdf", pdf, "application/pdf")},
        headers=other.headers,
    )

    assert response.json()["applied"] is True
    me = (await client.get(f"{API}/me", headers=other.headers)).json()
    assert me["last_name"] == "Сидоров"  # заполненное не перезаписано
    assert me["first_name"] == "Иван"
    skills = [s["name"] for s in me["skills"]]
    assert skills[0] == "Go"
    assert "FastAPI" in skills
    assert len(me["experience"]) == 2


async def test_import_rejects_non_pdf(client: AsyncClient, candidate: User) -> None:
    response = await client.post(
        f"{API}/me/resume/import",
        files={"file": ("resume.pdf", b"hello", "application/pdf")},
        headers=candidate.headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_pdf"


async def test_employer_pdf_respects_privacy(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    import io

    from pypdf import PdfReader

    await published_profile(client, candidate)

    response = await client.get(
        f"{API}/{candidate.id}/resume.pdf", headers=employer.headers
    )

    assert response.status_code == 200
    text = "".join(
        page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages
    )
    assert "Иванов" in text
    assert "+79123456789" not in text
