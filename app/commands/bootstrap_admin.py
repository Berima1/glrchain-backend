"""One-time initial administrator bootstrap.

Run only from a controlled administrative environment after migrations:
  APP_ENV=production GLRCHAIN_ALLOW_INITIAL_ADMIN_BOOTSTRAP=true
  GLRCHAIN_INITIAL_ADMIN_USERNAME=chosen_admin_username
  python -m app.commands.bootstrap_admin

Unset GLRCHAIN_ALLOW_INITIAL_ADMIN_BOOTSTRAP after success. This command does
not create a public HTTP endpoint and refuses if an admin already exists.
"""
import asyncio
import getpass
import os
import re
import sys

from passlib.context import CryptContext
from sqlalchemy import select

from app.audit import append_audit_event
from app.database import AsyncSessionLocal, engine
from app.models import User

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


async def bootstrap(username: str, password: str) -> None:
    if os.getenv("APP_ENV", "").strip().lower() not in {"prod", "production"}:
        raise RuntimeError("Initial admin bootstrap is permitted only with APP_ENV=production.")
    if os.getenv("GLRCHAIN_ALLOW_INITIAL_ADMIN_BOOTSTRAP") != "true":
        raise RuntimeError("Set GLRCHAIN_ALLOW_INITIAL_ADMIN_BOOTSTRAP=true for this controlled one-time operation.")
    expected_username = os.getenv("GLRCHAIN_INITIAL_ADMIN_USERNAME", "")
    if not expected_username or username != expected_username:
        raise RuntimeError("Username must match the separately configured GLRCHAIN_INITIAL_ADMIN_USERNAME.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", username):
        raise RuntimeError("Username must be 3-64 characters: letters, numbers, dot, underscore, or hyphen.")
    if len(password) < 16 or len(password) > 128:
        raise RuntimeError("Administrator password must be 16-128 characters.")

    async with AsyncSessionLocal() as db:
        existing_admin = await db.scalar(select(User.id).where(User.role == "admin").limit(1))
        if existing_admin is not None:
            raise RuntimeError("An administrator already exists; refusing initial bootstrap.")

        user = await db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(username=username, hashed_password=pwd_context.hash(password), role="admin")
            db.add(user)
            await db.flush()
        else:
            # Never promote a pre-existing public account silently; that could
            # grant control to someone who registered the chosen username first.
            raise RuntimeError("That username already exists. Choose an unused, controlled administrator username.")

        await append_audit_event(
            db,
            actor_user_id=user.id,
            action="admin.initial_bootstrap",
            object_type="user",
            object_id=str(user.id),
            details={"role": "admin", "method": "controlled_one_time_bootstrap"},
        )
        await db.commit()
        print(f"Initial administrator {username!r} created. Unset GLRCHAIN_ALLOW_INITIAL_ADMIN_BOOTSTRAP now.")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m app.commands.bootstrap_admin USERNAME", file=sys.stderr)
        return 2
    username = sys.argv[1]
    password = getpass.getpass("New administrator password (input hidden): ")
    confirm = getpass.getpass("Confirm administrator password: ")
    if password != confirm:
        print("Passwords did not match; no account was created.", file=sys.stderr)
        return 2
    try:
        asyncio.run(bootstrap(username, password))
    except Exception as exc:
        print(f"Bootstrap refused: {exc}", file=sys.stderr)
        return 1
    finally:
        asyncio.run(engine.dispose())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
