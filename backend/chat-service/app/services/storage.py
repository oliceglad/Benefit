"""Хранилище вложений.

``FileStorage`` — интерфейс: сейчас файлы лежат в локальном каталоге
(в docker — именованный том), для продакшена его можно заменить
S3-совместимым хранилищем (например, Yandex Object Storage), не меняя
остальной код.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

from app.core.config import settings

CHUNK_SIZE = 64 * 1024


class FileStorage(Protocol):
    async def save(self, data: bytes) -> str:
        """Сохраняет файл и возвращает ключ."""
        ...

    def open(self, key: str) -> AsyncIterator[bytes]: ...

    async def delete(self, key: str) -> None: ...


class LocalFileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        # Ключ генерируем сами (uuid), но всё равно не выпускаем путь за root.
        path = (self.root / key[:2] / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("Invalid storage key")
        return path

    async def save(self, data: bytes) -> str:
        key = uuid.uuid4().hex
        path = self._path(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(write)
        return key

    async def open(self, key: str) -> AsyncIterator[bytes]:
        path = self._path(key)
        handle = await asyncio.to_thread(path.open, "rb")
        try:
            while chunk := await asyncio.to_thread(handle.read, CHUNK_SIZE):
                yield chunk
        finally:
            handle.close()

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path(key).unlink, True)


def get_storage() -> FileStorage:
    return LocalFileStorage(settings.files_dir)
