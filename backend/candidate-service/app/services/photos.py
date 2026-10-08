"""Обработка фото профиля."""

import io

from fastapi import status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.core.exceptions import AppError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Защита от «пиксельных бомб»: картинка небольшого размера в байтах,
# но огромная в пикселях.
Image.MAX_IMAGE_PIXELS = 40_000_000


def process_photo(raw: bytes) -> bytes:
    """Проверяет изображение и перекодирует в JPEG.

    Перекодирование удаляет EXIF (в том числе геолокацию) и любые
    встроенные в файл данные, кроме самого изображения.
    """
    if len(raw) > settings.photo_max_bytes:
        raise AppError(
            "Фото должно быть не больше 5 МБ",
            code="photo_too_large",
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        )
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ALLOWED_FORMATS:
                raise UnidentifiedImageError
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
            image.thumbnail((settings.photo_max_side, settings.photo_max_side))
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=85, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise AppError(
            "Загрузите изображение в формате JPEG, PNG или WebP",
            code="invalid_photo",
            status_code=422,
        ) from exc
    return output.getvalue()
