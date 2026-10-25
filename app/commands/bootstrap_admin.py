"""One-time initial Firebase-backed administrator bootstrap.

Run only from a controlled administrative environment after database migrations.
The Firebase UID must be pre-approved out-of-band and must belong to a verified
Firebase user. This command is intentionally not exposed over HTTP.
"""
import asyncio
import os
import re
import sys

import firebase_admin
from firebase_admin import auth as firebase_auth
from sqlalchemy import select

from app.audit import append_audit_event
from app.database import AsyncSessionLocal, engine
from app.models import User
from app.routes.auth import FIREBASE_MANAGED_PASSWORD_MARKER


def _firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        project_id = os.getenv("FIREBASE_PROJECT_ID")
        if not project_id:
            raise RuntimeError("FIREBASE_PROJECT_ID is required.")
        return firebase_admin.initialize_app(options={"projectId": project_id})


async def bootstrap(username: str, firebase_uid: str) -> None:
    if os.getenv("APP_ENV", "").strip().lower() not in {"prod", "production"}:
        raise RuntimeError("Initial admin bootstrap is permitted only with APP_ENV=production.")
    if os.getenv("GLRCHAIN_ALLOW_INITIAL_ADMIN_BOOTSTRAP") != "true":
        raise RuntimeError("Set GLRCHAIN_ALLOW_INITIAL_ADMIN_BOOTSTRAP=true for this controlled one-time operation.")

    expected_username = os.getenv("GLRCHAIN_INITIAL_ADMIN_USERNAME", "")
    expected_uid = os.getenv("GLRCHAIN_INITIAL_ADMIN_FIREBASE_UID", "")
    if not expected_username or username != expected_username:
        raise RuntimeError("Username must match the separately configured GLRCHAIN_INITIAL_ADMIN_USERNAME.")
    if not expected_uid or firebase_uid != expected_uid:
        raise RuntimeError("Firebase UID must match the separately approved GLRCHAIN_INITIAL_ADMIN_FIREBASE_UID.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", username):
        raise RuntimeError("Username must be 3-64 characters: letters, numbers, dot, underscore, or hyphen.")
    if not firebase_uid or len(firebase_uid) > 128:
        raise RuntimeError("Firebase UID is invalid.")

    try:
        firebase_user = await asyncio.to_thread(
            firebase_auth.get_user, firebase_uid, app=_firebase_app()
        )
    except Exception as exc:
        raise RuntimeError("Could not verify the approved Firebase user in the configured project.") from exc

    if firebase_user.uid != firebase_uid:
        raise RuntimeError("Firebase returned a different UID; refusing bootstrap.")
    if not firebase_user.email or not firebase_user.email_verified:
        raise RuntimeError("The initial administrator Firebase account must have a verified email address.")

    async with AsyncSessionLocal() as db:
        existing_admin = await db.scalar(select(User.id).where(User.role == "admin").limit(1))
        if existing_admin is not None:
            raise RuntimeError("An administrator already exists; refusing initial bootstrap.")

        existing_uid = await db.scalar(select(User.id).where(User.firebase_uid == firebase_uid))
        if existing_uid is not None:
            raise RuntimeError("This Firebase UID already has a GLRChain profile; refusing privilege escalation.")
        existing_username = await db.scalar(select(User.id).where(User.username == username))
        if existing_username is not None:
            raise RuntimeError("That username already exists. Choose a separately approved unused username.")

        user = User(
            username=username,
            hashed_password=FIREBASE_MANAGED_PASSWORD_MARKER,
            firebase_uid=firebase_uid,
            role="admin",
        )
        db.add(user)
        await db.flush()
        await append_audit_event(
            db,
            actor_user_id=user.id,
            action="admin.initial_bootstrap",
            object_type="user",
            object_id=str(user.id),
            details={
                "role": "admin",
                "identity_provider": "firebase",
                "method": "controlled_one_time_bootstrap",
            },
        )
        await db.commit()
        print(f"Initial Firebase-backed administrator {username!r} created.")
        print("Unset GLRCHAIN_ALLOW_INITIAL_ADMIN_BOOTSTRAP and remove the one-time UID variable now.")


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: python -m app.commands.bootstrap_admin USERNAME FIREBASE_UID",
            file=sys.stderr,
        )
        return 2
    try:
        asyncio.run(bootstrap(sys.argv[1], sys.argv[2]))
    except Exception as exc:
        print(f"Bootstrap refused: {exc}", file=sys.stderr)
        return 1
    finally:
        asyncio.run(engine.dispose())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
