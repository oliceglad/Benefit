"""Проверка загружаемых файлов."""

import re
import unicodedata
from pathlib import PurePath

from benefit_common.errors import AppError

from app.core.config import settings

# Белый список: документы, изображения, архивы и исходный код.
# Тип отдаётся по расширению, а не по заявленному клиентом.
ALLOWED_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odt": "application/vnd.oasis.opendocument.text",
    "txt": "text/plain",
    "md": "text/markdown",
    "csv": "text/csv",
    "json": "application/json",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "zip": "application/zip",
    "py": "text/x-python",
    "ipynb": "application/x-ipynb+json",
    "sql": "application/sql",
    "java": "text/x-java",
    "kt": "text/plain",
    "go": "text/x-go",
    "ts": "text/plain",
    "tsx": "text/plain",
    "jsx": "text/plain",
    "cs": "text/plain",
    "cpp": "text/x-c++",
    "c": "text/x-c",
    "h": "text/x-c",
    "rs": "text/plain",
    "yaml": "text/yaml",
    "yml": "text/yaml",
}

# Сигнатуры исполняемых файлов: не принимаем их под любым расширением.
EXECUTABLE_SIGNATURES = (b"MZ", b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe")


def safe_filename(name: str) -> str:
    """Имя без путей и управляющих символов (для заголовка и отображения)."""
    name = unicodedata.normalize("NFC", PurePath(name.replace("\\", "/")).name)
    name = re.sub(r"[\x00-\x1f\x7f\"]", "", name).strip(" .")
    return name[:200] or "file"


def validate_upload(filename: str, data: bytes) -> tuple[str, str]:
    """Возвращает безопасное имя и Content-Type или выбрасывает ошибку."""
    if not data:
        raise AppError("Файл пустой", code="empty_file", status_code=422)
    if len(data) > settings.max_file_bytes:
        raise AppError(
            f"Файл больше {settings.max_file_bytes // (1024 * 1024)} МБ",
            code="file_too_large",
            status_code=413,
        )
    name = safe_filename(filename)
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    content_type = ALLOWED_TYPES.get(extension)
    if content_type is None or data.startswith(EXECUTABLE_SIGNATURES):
        raise AppError(
            "Такой тип файла нельзя отправить",
            code="file_type_not_allowed",
            status_code=415,
        )
    return name, content_type
