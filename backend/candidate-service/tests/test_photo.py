import io

from httpx import AsyncClient
from PIL import Image

from tests.conftest import API, User, published_profile


def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (1600, 1200)) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", size, (37, 99, 235))
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera"  # Make
    image.save(buffer, format=fmt, exif=exif)
    return buffer.getvalue()


async def upload(client: AsyncClient, user: User, content: bytes) -> int:
    response = await client.put(
        f"{API}/me/photo",
        files={"file": ("photo.png", content, "image/png")},
        headers=user.headers,
    )
    return response.status_code


async def test_photo_is_resized_and_stripped(
    client: AsyncClient, candidate: User
) -> None:
    assert await upload(client, candidate, image_bytes()) == 204

    response = await client.get(f"{API}/me/photo", headers=candidate.headers)

    assert response.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(response.content)) as image:
        assert max(image.size) == 800
        assert not image.getexif()
    me = await client.get(f"{API}/me", headers=candidate.headers)
    assert me.json()["has_photo"] is True


async def test_rejects_non_images(client: AsyncClient, candidate: User) -> None:
    assert await upload(client, candidate, b"%PDF-1.4 not an image") == 422


async def test_employer_photo_respects_privacy(
    client: AsyncClient, candidate: User, employer: User
) -> None:
    await upload(client, candidate, image_bytes("JPEG", (300, 300)))
    await published_profile(client, candidate)
    url = f"{API}/{candidate.id}/photo"

    assert (await client.get(url, headers=employer.headers)).status_code == 200

    await client.patch(
        f"{API}/me", json={"privacy": {"show_photo": False}}, headers=candidate.headers
    )
    assert (await client.get(url, headers=employer.headers)).status_code == 404


async def test_delete_photo(client: AsyncClient, candidate: User) -> None:
    await upload(client, candidate, image_bytes())

    await client.delete(f"{API}/me/photo", headers=candidate.headers)

    response = await client.get(f"{API}/me/photo", headers=candidate.headers)
    assert response.status_code == 404
