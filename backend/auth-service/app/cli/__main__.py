"""Административные команды auth-service.

``python -m app.cli create-admin admin@benefit.ru [--password ...]`` —
создать администратора или выдать роль admin существующему пользователю.
Без ``--password`` пароль запрашивается в терминале.
"""

import argparse
import asyncio
import getpass
import sys
from datetime import UTC, datetime

from app.core.security import hash_password
from app.db.session import async_session_factory, engine
from app.models.user import User, UserRole
from app.repositories.users import UserRepository


async def create_admin(email: str, password: str | None) -> None:
    email = email.strip().lower()
    async with async_session_factory() as session:
        user = await UserRepository(session).get_by_email(email)
        if user is None:
            if not password:
                password = getpass.getpass("Пароль администратора: ")
            if len(password) < 8:
                sys.exit("Пароль должен быть не короче 8 символов")
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                email_verified_at=datetime.now(UTC),
            )
            session.add(user)
            action = "создан"
        else:
            user.role = UserRole.ADMIN
            if password:
                user.password_hash = hash_password(password)
            action = "получил роль admin"
        await session.commit()
    await engine.dispose()
    print(f"{email}: {action}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="создать администратора")
    admin.add_argument("email")
    admin.add_argument("--password")
    args = parser.parse_args()
    if args.command == "create-admin":
        asyncio.run(create_admin(args.email, args.password))


main()
