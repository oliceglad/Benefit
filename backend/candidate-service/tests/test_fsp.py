from httpx import AsyncClient

from tests.conftest import API, FakeFsp, User, published_profile

ACHIEVEMENT = {
    "id": "ach-1",
    "event": "Чемпионат России по продуктовому программированию",
    "discipline": "Продуктовое программирование",
    "level": "federal",
    "result": "winner",
    "place": 1,
    "team": "ByteForce",
    "date": "2025-11-23",
    "url": None,
}


async def test_sync_without_linked_fsp_id(
    client: AsyncClient, candidate: User, fsp: FakeFsp
) -> None:
    response = await client.post(f"{API}/me/fsp/sync", headers=candidate.headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "fsp_not_linked"


async def test_sync_loads_achievements(
    client: AsyncClient, candidate: User, employer: User, fsp: FakeFsp
) -> None:
    fsp.linked[candidate.id] = "fsp-42"
    fsp.items["fsp-42"] = [ACHIEVEMENT]

    response = await client.post(f"{API}/me/fsp/sync", headers=candidate.headers)

    assert response.status_code == 200
    info = response.json()["fsp"]
    assert info["linked"] is True
    assert info["participant_id"] == "fsp-42"
    assert info["achievements"][0]["event"] == ACHIEVEMENT["event"]

    await published_profile(client, candidate)
    public = await client.get(f"{API}/{candidate.id}", headers=employer.headers)
    assert len(public.json()["fsp_achievements"]) == 1

    await client.patch(
        f"{API}/me",
        json={"privacy": {"show_fsp_achievements": False}},
        headers=candidate.headers,
    )
    public = await client.get(f"{API}/{candidate.id}", headers=employer.headers)
    assert public.json()["fsp_achievements"] == []


async def test_unlinking_clears_achievements(
    client: AsyncClient, candidate: User, fsp: FakeFsp
) -> None:
    fsp.linked[candidate.id] = "fsp-42"
    fsp.items["fsp-42"] = [ACHIEVEMENT]
    await client.post(f"{API}/me/fsp/sync", headers=candidate.headers)

    del fsp.linked[candidate.id]
    await client.post(f"{API}/me/fsp/sync", headers=candidate.headers)

    me = (await client.get(f"{API}/me", headers=candidate.headers)).json()
    assert me["fsp"] == {
        "linked": False,
        "participant_id": None,
        "synced_at": None,
        "achievements": [],
    }
