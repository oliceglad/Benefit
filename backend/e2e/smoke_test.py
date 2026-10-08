"""Сквозная проверка связности сервисов через API-шлюз.

Запуск (стек поднят через ``docker compose up``)::

    python backend/e2e/smoke_test.py [--gateway http://localhost:8000]

Нужны пакеты ``httpx`` и ``httpx-ws``. Сценарий создаёт новых пользователей, поэтому
его можно запускать повторно. Проверяет всю цепочку:

auth (регистрация, код из письма) → candidate (профиль, согласия, публикация)
→ assessment (опрос, тест с таймингом) → candidate (категория из результата)
→ notification + mail (уведомление и письмо) → applications (приглашение,
ответ) → notification (уведомление работодателю) → chat (WebSocket, файлы,
регулярное задание) → assessment (тест работодателя в переписке)
→ candidate (актуальность профиля).
"""

import argparse
import re
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from httpx_ws import connect_ws

MAILPIT = "http://localhost:8025"


class Smoke:
    def __init__(self, gateway: str) -> None:
        self.gateway = gateway.rstrip("/")
        self.http = httpx.Client(base_url=self.gateway, timeout=30)
        self.stamp = int(time.time() * 1000)

    def step(self, title: str) -> None:
        print(f"\n▶ {title}")

    def ok(self, message: str) -> None:
        print(f"  ✓ {message}")

    def check(self, response: httpx.Response, status: int = 200) -> Any:
        if response.status_code != status:
            raise AssertionError(
                f"{response.request.method} {response.request.url} → "
                f"{response.status_code}: {response.text[:500]}"
            )
        return response.json() if response.content else None

    def wait_for(self, what: str, probe: Callable[[], Any], timeout: float = 30) -> Any:
        """Ждёт асинхронной доставки (outbox доставляет раз в ~2 с)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = probe()
            if result:
                return result
            time.sleep(1)
        raise AssertionError(f"Не дождались: {what}")

    def mail_to(self, email: str, subject_part: str) -> dict[str, Any] | None:
        messages = httpx.get(
            f"{MAILPIT}/api/v1/search", params={"query": f"to:{email}"}
        ).json()["messages"]
        return next((m for m in messages if subject_part in m["Subject"]), None)

    def register(self, role: str, name: str = "") -> tuple[dict[str, str], str]:
        email = f"smoke-{role}{name}-{self.stamp}@mail.ru"
        self.check(
            self.http.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "secret123", "role": role},
            ),
            201,
        )
        mail = self.wait_for("письмо с кодом", lambda: self.mail_to(email, "код"))
        code = re.search(r"\d{6}", mail["Subject"]).group()
        tokens = self.check(
            self.http.post(
                "/api/v1/auth/verify-email", json={"email": email, "code": code}
            )
        )
        return {"Authorization": f"Bearer {tokens['access_token']}"}, email

    def run(self) -> None:
        self.step("Регистрация кандидата и работодателя (auth → mail)")
        candidate, candidate_email = self.register("candidate")
        employer, _ = self.register("employer")
        self.ok("коды подтверждения пришли на почту, токены получены")

        self.step("Профиль кандидата (candidate-service)")
        me = self.check(self.http.get("/api/v1/candidates/me", headers=candidate))
        candidate_id = me["user_id"]
        self.check(
            self.http.patch(
                "/api/v1/candidates/me",
                json={
                    "last_name": "Смоуков",
                    "first_name": "Тест",
                    "phone": "+79990000000",
                    "headline": "Python Backend-разработчик",
                    "grade": "middle",
                    "roles": ["backend"],
                    "skills": [{"name": "Python"}, {"name": "PostgreSQL"}],
                    "projects": [{"name": "Benefit", "technologies": ["Python"]}],
                },
                headers=candidate,
            )
        )
        for consent in self.check(
            self.http.get("/api/v1/candidates/me/consents", headers=candidate)
        ):
            self.check(
                self.http.post(
                    "/api/v1/candidates/me/consents",
                    json={
                        "type": consent["type"],
                        "version": consent["required_version"],
                    },
                    headers=candidate,
                )
            )
        profile = self.check(
            self.http.post("/api/v1/candidates/me/publish", headers=candidate)
        )
        assert profile["category"]["grade_status"] == "not_confirmed"
        self.ok("профиль опубликован, грейд middle пока не подтверждён")

        self.step("Опрос и тестирование (assessment → candidate)")
        survey = self.check(
            self.http.get("/api/v1/assessments/survey", headers=candidate)
        )
        assert survey["prefill"]["claimed_grade"] == "middle", survey["prefill"]
        self.ok("опрос предзаполнен из профиля")
        attempt = self.check(
            self.http.post(
                "/api/v1/assessments/attempts",
                json={
                    "industry": "fintech",
                    "specialization": "backend",
                    "target_grade": "middle",
                    "years_of_experience": 3,
                    "skills": ["Python"],
                },
                headers=candidate,
            ),
            201,
        )
        url = f"/api/v1/assessments/attempts/{attempt['id']}"
        while True:
            task = self.check(self.http.get(f"{url}/current-task", headers=candidate))
            answer = "ответ" if task["kind"] == "text" else [task["options"][0]["id"]]
            reply = self.check(
                self.http.post(
                    f"{url}/answers",
                    json={"attempt_task_id": task["attempt_task_id"], "answer": answer},
                    headers=candidate,
                )
            )
            if reply["finished"]:
                break
        result = reply["attempt"]["result"]
        timings = [t["time_spent_seconds"] for t in result["tasks"]]
        assert all(t is not None for t in timings)
        self.ok(
            f"тест завершён: {result['score']:g}/{result['max_score']} баллов "
            f"({result['percent']}%), итог {result['outcome']}, "
            f"время {result['duration_seconds']} с"
        )

        def category() -> dict[str, Any] | None:
            data = self.check(
                self.http.get(f"/api/v1/candidates/{candidate_id}", headers=employer)
            )
            return data["category"] if data["category"]["industry"] else None

        seen = self.wait_for("категория в профиле", category)
        expected = (
            "not_confirmed" if result["outcome"] == "not_confirmed" else "confirmed"
        )
        assert seen["grade_status"] == expected, seen
        assert seen["industry"] == "fintech"
        if expected == "not_confirmed":
            assert seen["grade"] == "middle"  # низкий результат не показывается
        self.ok(
            f"работодатель видит категорию: {seen['grade']} ({seen['grade_status']})"
        )

        self.step("Уведомление о результате (notification → mail)")
        self.wait_for(
            "уведомление о тесте",
            lambda: [
                n
                for n in self.check(
                    self.http.get("/api/v1/notifications", headers=candidate)
                )["items"]
                if n["type"] == "assessment.completed"
            ],
        )
        self.wait_for(
            "письмо о результате",
            lambda: (
                self.mail_to(candidate_email, "Грейд")
                or self.mail_to(candidate_email, "Тест пройден")
            ),
        )
        self.ok("уведомление в кабинете и письмо доставлены")

        self.step("Работодатель: компания, потребность, подборка (employer → matching)")
        self.check(
            self.http.put(
                "/api/v1/employers/company",
                json={
                    "name": "ООО Смоук",
                    "industry": "fintech",
                    "description": "Платёжные сервисы для малого бизнеса.",
                    "contact_email": "hr@smoke-test.ru",
                },
                headers=employer,
            )
        )
        need = self.check(
            self.http.post(
                "/api/v1/employers/needs",
                json={
                    "title": "Python-разработчик в команду платежей",
                    "team_description": "Сервисы приёма платежей.",
                    "specialization": "backend",
                    "grade": "middle",
                    "required_skills": ["питон", "PostgreSQL"],
                },
                headers=employer,
            ),
            201,
        )

        def matched() -> dict[str, Any] | None:
            result = self.check(
                self.http.get(
                    f"/api/v1/employers/needs/{need['id']}/matches",
                    params={"limit": 100},
                    headers=employer,
                )
            )
            return next(
                (
                    c
                    for c in result["candidates"]
                    if c["candidate"]["user_id"] == candidate_id
                ),
                None,
            )

        found = self.wait_for("кандидат в подборке", matched)
        assert any("Стек: Python, PostgreSQL" in r for r in found["reasons"]), found
        assert "phone" not in found["candidate"]
        assert found["fit"] in ("excellent", "good", "partial")
        assert {p["component"] for p in found["breakdown"]} >= {
            "required_skills",
            "specialization",
            "grade",
        }
        self.check(
            self.http.put(
                f"/api/v1/employers/needs/{need['id']}/feedback/{candidate_id}",
                json={"verdict": "like"},
                headers=employer,
            )
        )
        liked = matched()
        assert liked is not None and liked["feedback"] == "like"
        self.ok(
            f"кандидат в подборке: {found['score']} баллов, обоснование: "
            f"{found['reasons'][0]}"
        )
        page = self.check(
            self.http.get(
                "/api/v1/talent/candidates",
                params={
                    "specialization": "backend",
                    "skills": ["python"],
                    "q": "разработчик",
                },
                headers=employer,
            )
        )
        assert candidate_id in [item["user_id"] for item in page["items"]], (
            f"кандидата нет в поиске: total={page['total']}"
        )
        self.ok(
            f"поиск по банку кандидатов: найдено {page['total']}, "
            f"категорий {len(page['categories'])}"
        )

        self.step("Приглашение работодателя (applications → notification → mail)")
        invitation = self.check(
            self.http.post(
                "/api/v1/invitations",
                json={
                    "candidate_id": candidate_id,
                    # Компания подставится из профиля компании работодателя.
                    "vacancy": {
                        "title": "Python-разработчик",
                        "salary_from": 250000,
                        "salary_to": 350000,
                    },
                },
                headers=employer,
            ),
            201,
        )
        assert invitation["vacancy"]["company_name"] == "ООО Смоук"
        incoming = self.check(
            self.http.get("/api/v1/invitations/incoming", headers=candidate)
        )
        assert [i["id"] for i in incoming] == [invitation["id"]]
        hidden = self.check(
            self.http.get(f"/api/v1/candidates/{candidate_id}", headers=employer)
        )
        assert hidden["phone"] is None, "контакты видны до принятия приглашения"
        self.wait_for(
            "письмо о приглашении",
            lambda: self.mail_to(candidate_email, "Приглашение на вакансию"),
        )
        self.ok("кандидат видит приглашение, письмо пришло")
        self.check(
            self.http.post(
                f"/api/v1/invitations/{invitation['id']}/accept",
                json={"message": "Готов к собеседованию"},
                headers=candidate,
            )
        )
        self.wait_for(
            "уведомление работодателю",
            lambda: self.check(
                self.http.get("/api/v1/notifications/unread-count", headers=employer)
            )["unread_count"],
        )
        self.ok("приглашение принято, работодатель получил уведомление")

        def contacts() -> dict[str, Any] | None:
            data = self.check(
                self.http.get(f"/api/v1/candidates/{candidate_id}", headers=employer)
            )
            return data if data["contact_access"] == "granted" else None

        shared = self.wait_for("контакты для работодателя", contacts)
        assert shared["phone"] == "+79990000000", shared
        self.ok("контакты кандидата открылись работодателю (applications → candidate)")

        self.step("Переписка по WebSocket и файлы (applications → chat)")
        conversation = self.wait_for(
            "диалог по приглашению",
            lambda: self.check(
                self.http.get(
                    "/api/v1/chat/conversations",
                    params={"invitation_id": invitation["id"]},
                    headers=candidate,
                )
            ),
        )[0]
        chat_url = f"/api/v1/chat/conversations/{conversation['id']}"
        ws_url = f"{self.gateway}/api/v1/chat/ws"
        token = candidate["Authorization"].removeprefix("Bearer ")
        with connect_ws(ws_url, self.http) as ws:
            ws.send_json({"type": "auth", "token": token})
            assert ws.receive_json(timeout=10)["type"] == "ready"
            self.check(
                self.http.post(
                    f"{chat_url}/messages",
                    json={"text": "Когда удобно созвониться?"},
                    headers=employer,
                ),
                201,
            )
            while (event := ws.receive_json(timeout=10))["type"] != "message.created":
                pass
            assert event["message"]["text"] == "Когда удобно созвониться?"
            self.ok("сообщение работодателя пришло кандидату по WebSocket")

            attachment = self.check(
                self.http.post(
                    f"{chat_url}/attachments",
                    files={"file": ("portfolio.md", b"# Projects", "text/markdown")},
                    headers=candidate,
                ),
                201,
            )
            ws.send_json(
                {
                    "type": "message.send",
                    "conversation_id": conversation["id"],
                    "text": "Завтра в 11:00, портфолио во вложении",
                    "attachment_ids": [attachment["id"]],
                    "client_id": f"smoke-{self.stamp}",
                }
            )
            while (event := ws.receive_json(timeout=10))["type"] != "message.ack":
                pass
        downloaded = self.http.get(
            f"/api/v1/chat/attachments/{attachment['id']}", headers=employer
        )
        assert downloaded.content == b"# Projects", downloaded.status_code
        self.ok("кандидат ответил по WebSocket с файлом, работодатель его скачал")

        self.step("Регулярное задание (chat → candidate)")
        task = self.check(
            self.http.post(
                f"{chat_url}/tasks",
                json={
                    "title": "Оптимизировать запрос",
                    "description": "Предложите, как ускорить отчёт по заказам.",
                    "due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                    "recurrence_days": 7,
                },
                headers=employer,
            ),
            201,
        )
        self.check(
            self.http.post(
                f"/api/v1/chat/tasks/{task['id']}/submit",
                json={"response_type": "approach", "text": "Индекс + материализация"},
                headers=candidate,
            )
        )
        self.check(
            self.http.post(
                f"/api/v1/chat/tasks/{task['id']}/review",
                json={"result": "passed", "score": 85, "feedback": "Хорошо"},
                headers=employer,
            )
        )

        def actuality() -> dict[str, Any] | None:
            data = self.check(
                self.http.get(f"/api/v1/candidates/{candidate_id}", headers=employer)
            )["actuality"]
            return data if data["tasks_passed"] else None

        fresh = self.wait_for("актуальность профиля", actuality)
        assert fresh["status"] == "active" and fresh["tasks_submitted"] == 1
        self.ok("задание выдано, решено и принято — актуальность профиля обновилась")

        self.step("Тест работодателя (assessment → chat → candidate)")
        options = [{"id": "a", "text": "Верно"}, {"id": "b", "text": "Неверно"}]
        own_test = self.check(
            self.http.post(
                "/api/v1/assessments/employer/tests",
                json={
                    "title": "Скрининг ООО Смоук",
                    "specialization": "backend",
                    "grade": "middle",
                    "time_limit_seconds": 600,
                    "tasks": [
                        {
                            "key": "q1",
                            "kind": "single_choice",
                            "prompt": "Вопрос 1",
                            "options": options,
                            "correct": ["a"],
                            "points": 10,
                            "time_limit_seconds": 60,
                        },
                        {
                            "key": "q2",
                            "kind": "text",
                            "prompt": "Вопрос 2",
                            "correct": ["ответ"],
                            "points": 5,
                            "time_limit_seconds": 60,
                        },
                    ],
                },
                headers=employer,
            ),
            201,
        )
        sent = self.check(
            self.http.post(
                f"/api/v1/assessments/employer/tests/{own_test['id']}/assignments",
                json={
                    "conversation_id": conversation["id"],
                    "due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                },
                headers=employer,
            ),
            201,
        )

        def card() -> list[dict[str, Any]]:
            history = self.check(
                self.http.get(f"{chat_url}/messages", headers=candidate)
            )
            return [m for m in history if m["kind"] == "assessment"]

        assert (
            self.wait_for("карточка теста в переписке", card)[0]["data"][
                "assignment_id"
            ]
            == sent["id"]
        )
        self.ok("тест отправлен, карточка появилась в переписке")
        employer_attempt = self.check(
            self.http.post(
                f"/api/v1/assessments/assignments/{sent['id']}/start", headers=candidate
            )
        )
        attempt_url = f"/api/v1/assessments/attempts/{employer_attempt['id']}"
        while True:
            task = self.check(
                self.http.get(f"{attempt_url}/current-task", headers=candidate)
            )
            answer = "ответ" if task["kind"] == "text" else ["a"]
            reply = self.check(
                self.http.post(
                    f"{attempt_url}/answers",
                    json={"attempt_task_id": task["attempt_task_id"], "answer": answer},
                    headers=candidate,
                )
            )
            if reply["finished"]:
                break
        review = self.check(
            self.http.get(
                f"/api/v1/assessments/employer/assignments/{sent['id']}",
                headers=employer,
            )
        )
        assert review["result"]["percent"] == 100
        assert all(a["is_correct"] and a["answer"] for a in review["answers"])

        def counted() -> dict[str, Any] | None:
            data = self.check(
                self.http.get(f"/api/v1/candidates/{candidate_id}", headers=employer)
            )["actuality"]
            return data if data["employer_tests_completed"] else None

        self.wait_for("тест работодателя в актуальности", counted)
        self.ok("кандидат прошёл тест (100%), работодатель видит ответы и время")

        self.step("Вакансия и отклик (employer → applications → chat)")
        vacancy = self.check(
            self.http.post(
                "/api/v1/employers/vacancies",
                json={
                    "title": "Senior Python Developer",
                    "description": "Архитектура платёжных сервисов.",
                    "specialization": "backend",
                    "grade": "senior",
                    "skills": ["Python", "Kafka"],
                    "salary_from": 400000,
                },
                headers=employer,
            ),
            201,
        )
        self.check(
            self.http.patch(
                f"/api/v1/employers/vacancies/{vacancy['id']}",
                json={"status": "published"},
                headers=employer,
            )
        )
        listed = self.check(
            self.http.get(
                "/api/v1/vacancies", params={"skill": "kafka"}, headers=candidate
            )
        )
        assert vacancy["id"] in [v["id"] for v in listed["items"]]
        application = self.check(
            self.http.post(
                "/api/v1/applications",
                json={
                    "vacancy_id": vacancy["id"],
                    "cover_letter": "Хочу расти в архитектуре",
                },
                headers=candidate,
            ),
            201,
        )
        received = self.check(
            self.http.get(
                "/api/v1/applications/received",
                params={"vacancy_id": vacancy["id"]},
                headers=employer,
            )
        )
        assert [a["id"] for a in received] == [application["id"]]
        self.check(
            self.http.post(
                f"/api/v1/applications/{application['id']}/status",
                json={"status": "invited", "message": "Ждём на собеседование"},
                headers=employer,
            )
        )
        self.wait_for(
            "переписка по отклику",
            lambda: [
                c
                for c in self.check(
                    self.http.get("/api/v1/chat/conversations", headers=candidate)
                )
                if c["source"] == "application"
            ],
        )
        mine = self.check(self.http.get("/api/v1/applications", headers=candidate))
        assert mine[0]["status"] == "invited"
        self.ok("вакансия опубликована, кандидат откликнулся, работодатель пригласил")

        self.step("Ограничения доступа")
        stranger, _ = self.register("candidate", "-stranger")
        checks = {
            "чужое приглашение": self.http.get(
                f"/api/v1/invitations/{invitation['id']}", headers=stranger
            ).status_code
            == 404,
            "чужая попытка теста": self.http.get(url, headers=stranger).status_code
            == 404,
            "чужой профиль": self.http.get(
                f"/api/v1/candidates/{candidate_id}", headers=stranger
            ).status_code
            == 403,
            "чужая переписка": self.http.get(chat_url, headers=stranger).status_code
            == 404,
            "чужое вложение": self.http.get(
                f"/api/v1/chat/attachments/{attachment['id']}", headers=stranger
            ).status_code
            == 404,
            "внутренний API снаружи": self.http.get("/internal/v1/events").status_code
            == 404,
        }
        failed = [name for name, passed in checks.items() if not passed]
        assert not failed, failed
        self.ok("кандидат не видит чужие данные, /internal закрыт")
        print("\nВсе сервисы связаны корректно ✔")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", default="http://localhost:8000")
    args = parser.parse_args()
    try:
        Smoke(args.gateway).run()
    except AssertionError as exc:
        print(f"\n✗ {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
