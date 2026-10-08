from httpx import AsyncClient

from tests.conftest import API, FULL_PROFILE, User, grant_consents, published_profile


async def test_first_visit_creates_draft_with_onboarding(
    client: AsyncClient, candidate: User
) -> None:
    response = await client.get(f"{API}/me", headers=candidate.headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert body["contact_email"] == "candidate@mail.ru"
    completeness = body["completeness"]
    assert completeness["can_publish"] is False
    assert completeness["next_step"] == "personal"
    assert [s["id"] for s in completeness["steps"]][:2] == ["personal", "contacts"]
    # Почта из токена уже заполнила шаг «Контакты».
    assert {s["id"]: s["completed"] for s in completeness["steps"]}["contacts"]


async def test_access_requires_candidate_role(
    client: AsyncClient, employer: User
) -> None:
    assert (await client.get(f"{API}/me")).status_code == 401
    assert (await client.get(f"{API}/me", headers=employer.headers)).status_code == 403


async def test_update_normalizes_values(client: AsyncClient, candidate: User) -> None:
    response = await client.patch(
        f"{API}/me", json=FULL_PROFILE, headers=candidate.headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["phone"] == "+79123456789"
    assert body["telegram"] == "@ivanov_dev"
    assert [s["name"] for s in body["skills"]] == [
        "Python",
        "FastAPI",
        "PostgreSQL",
        "Docker",
    ]
    assert body["age"] is not None
    # Опыт: стажировка 06.2021–02.2022 (9 мес.) + с 03.2022 по сей день.
    assert body["total_experience_months"] > 9
    assert body["completeness"]["missing_required"] == ["consents"]


async def test_partial_update_keeps_other_fields(
    client: AsyncClient, candidate: User
) -> None:
    await client.patch(f"{API}/me", json=FULL_PROFILE, headers=candidate.headers)

    response = await client.patch(
        f"{API}/me", json={"grade": "senior"}, headers=candidate.headers
    )

    assert response.json()["grade"] == "senior"
    assert response.json()["last_name"] == "Иванов"


async def test_validation_errors(client: AsyncClient, candidate: User) -> None:
    cases = [
        {"birth_date": "2020-01-01"},
        {"phone": "12345"},
        {"grade": "god"},
        {"roles": ["astronaut"]},
        {"unknown_field": 1},
        {
            "experience": [
                {
                    "company": "A",
                    "position": "B",
                    "start_date": "2022-01-01",
                    "end_date": "2021-01-01",
                }
            ]
        },
    ]
    for payload in cases:
        response = await client.patch(
            f"{API}/me", json=payload, headers=candidate.headers
        )
        assert response.status_code == 422, payload


async def test_experience_overlap_counted_once(
    client: AsyncClient, candidate: User
) -> None:
    job = {"company": "A", "position": "Dev"}
    response = await client.patch(
        f"{API}/me",
        json={
            "experience": [
                {**job, "start_date": "2020-01-01", "end_date": "2020-12-01"},
                {**job, "start_date": "2020-06-01", "end_date": "2021-05-01"},
            ]
        },
        headers=candidate.headers,
    )
    assert response.json()["total_experience_months"] == 17


async def test_publish_requires_required_fields_and_consents(
    client: AsyncClient, candidate: User
) -> None:
    response = await client.post(f"{API}/me/publish", headers=candidate.headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "profile_incomplete"

    await client.patch(f"{API}/me", json=FULL_PROFILE, headers=candidate.headers)
    response = await client.post(f"{API}/me/publish", headers=candidate.headers)
    assert response.status_code == 422
    assert "consents" in response.json()["error"]["message"]

    await grant_consents(client, candidate)
    response = await client.post(f"{API}/me/publish", headers=candidate.headers)
    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["completeness"]["onboarding_completed"] is True


async def test_published_profile_cannot_lose_required_fields(
    client: AsyncClient, candidate: User
) -> None:
    await published_profile(client, candidate)

    response = await client.patch(
        f"{API}/me", json={"skills": []}, headers=candidate.headers
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "profile_incomplete"


async def test_consent_with_outdated_version_rejected(
    client: AsyncClient, candidate: User
) -> None:
    response = await client.post(
        f"{API}/me/consents",
        json={"type": "personal_data", "version": "1999-01-01"},
        headers=candidate.headers,
    )
    assert response.status_code == 409


async def test_revoking_consent_unpublishes(
    client: AsyncClient, candidate: User
) -> None:
    await published_profile(client, candidate)

    response = await client.delete(
        f"{API}/me/consents/publication", headers=candidate.headers
    )

    assert response.status_code == 200
    statuses = {s["type"]: s["granted"] for s in response.json()}
    assert statuses == {"personal_data": True, "publication": False}
    me = await client.get(f"{API}/me", headers=candidate.headers)
    assert me.json()["status"] == "draft"


async def test_employer_sees_only_published_profiles(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await client.patch(f"{API}/me", json=FULL_PROFILE, headers=candidate.headers)
    url = f"{API}/{candidate.id}"

    assert (await client.get(url, headers=employer.headers)).status_code == 404

    await grant_consents(client, candidate)
    await client.post(f"{API}/me/publish", headers=candidate.headers)
    response = await client.get(url, headers=employer.headers)

    assert response.status_code == 200
    body = response.json()
    # Контакты закрыты до принятия приглашения или отклика.
    assert (body["phone"], body["contact_access"]) == (None, "hidden")
    assert "birth_date" not in body
    assert "privacy" not in body


async def test_privacy_settings_applied_for_employer(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(
        client,
        candidate,
        privacy={
            "show_birth_date": False,
            "show_salary": False,
            "hide_current_company": True,
        },
    )

    body = (await client.get(f"{API}/{candidate.id}", headers=employer.headers)).json()

    assert body["phone"] is None
    assert body["contact_email"] is None
    assert body["telegram"] is None
    assert body["age"] is None
    assert body["salary_from"] is None
    companies = [job["company"] for job in body["experience"]]
    assert companies == ["Компания скрыта", "Яндекс"]


async def test_candidate_cannot_view_other_candidates(
    client: AsyncClient, candidate: User
) -> None:
    other = User("candidate", "other@mail.ru")
    await published_profile(client, other)

    response = await client.get(f"{API}/{other.id}", headers=candidate.headers)

    assert response.status_code == 403


async def test_delete_profile(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await published_profile(client, candidate)

    response = await client.delete(f"{API}/me", headers=candidate.headers)

    assert response.status_code == 204
    assert (
        await client.get(f"{API}/{candidate.id}", headers=employer.headers)
    ).status_code == 404
    consents = await client.get(f"{API}/me/consents", headers=candidate.headers)
    assert not any(c["granted"] for c in consents.json())


async def test_dictionaries(client: AsyncClient) -> None:
    body = (await client.get(f"{API}/dictionaries")).json()
    assert {"id": "middle", "title": "Middle"} in body["grades"]
    assert body["soft_skills"]

    skills = (await client.get(f"{API}/dictionaries/skills?q=питон")).json()
    assert skills == ["Python"]
    skills = (await client.get(f"{API}/dictionaries/skills?q=post")).json()
    assert "PostgreSQL" in skills
