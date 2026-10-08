"""Команды управления контентом тестов.

    python -m app.cli import <файл.json|каталог> [--skip-existing]
    python -m app.cli export <файл.json>

Пакеты содержат правильные ответы: храните их вне репозитория.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import async_session_factory, engine
from app.schemas.content import TestPack
from app.services.content import ContentService


def _pack_files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.glob("*.json"))
    return [path]


async def import_content(path: Path, skip_existing: bool) -> None:
    files = _pack_files(path)
    if not files:
        print(f"{path}: пакетов тестов нет")
        return
    async with async_session_factory() as session:
        for file in files:
            try:
                pack = TestPack.model_validate_json(file.read_text("utf-8"))
            except ValidationError as exc:
                sys.exit(f"{file}: некорректный пакет\n{exc}")
            report = await ContentService(session).import_pack(
                pack, None, skip_existing=skip_existing
            )
            print(
                f"{file.name}: создано {report.created}, обновлено {report.updated}, "
                f"пропущено {report.skipped}"
            )


async def export_content(path: Path) -> None:
    async with async_session_factory() as session:
        pack = await ContentService(session).export()
    path.write_text(
        json.dumps(pack.model_dump(mode="json"), ensure_ascii=False, indent=2), "utf-8"
    )
    print(f"{path}: выгружено тестов — {len(pack.tests)}")


async def run(args: argparse.Namespace) -> None:
    try:
        if args.command == "import":
            await import_content(Path(args.path), args.skip_existing)
        else:
            await export_content(Path(args.path))
    finally:
        await engine.dispose()


def main() -> None:
    setup_logging(settings.log_level)
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import", help="импортировать пакет тестов")
    importer.add_argument("path")
    importer.add_argument("--skip-existing", action="store_true")
    exporter = commands.add_parser("export", help="выгрузить все тесты")
    exporter.add_argument("path")
    asyncio.run(run(parser.parse_args()))


main()
