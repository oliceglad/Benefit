"""Validation and sanitising for company logos."""

import io

from benefit_common.errors import AppError
from fastapi import status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 40_000_000


def process_company_logo(raw: bytes) -> tuple[bytes, str]:
    """Decode, resize and re-encode a supported image without metadata."""
    if len(raw) > settings.logo_max_bytes:
        raise AppError(
            "Логотип должен быть не больше 5 МБ",
            code="logo_too_large",
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        )
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise UnidentifiedImageError
            source = ImageOps.exif_transpose(source)
            has_alpha = source.mode in {"RGBA", "LA"} or "transparency" in source.info
            image = source.convert("RGBA" if has_alpha else "RGB")
            image.thumbnail((settings.logo_max_side, settings.logo_max_side))
            output = io.BytesIO()
            if has_alpha:
                image.save(output, format="PNG", optimize=True)
                content_type = "image/png"
            else:
                image.save(output, format="JPEG", quality=88, optimize=True)
                content_type = "image/jpeg"
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise AppError(
            "Загрузите изображение в формате JPEG, PNG или WebP",
            code="invalid_logo",
            status_code=422,
        ) from exc
    return output.getvalue(), content_type
