import asyncio
import os
from datetime import datetime, timedelta, timezone

import firebase_admin
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import append_audit_event
from app.database import get_db
from app.models import User
from app.schemas import FirebaseProvision, Token, UserCreate, UserLogin, UserOut

router = APIRouter()
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
DUMMY_PASSWORD_HASH = pwd_context.hash("glrchain-login-timing-only-not-a-user-password")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
FIREBASE_MANAGED_PASSWORD_MARKER = "FIREBASE_AUTH_MANAGED_NO_LOCAL_PASSWORD"


def _auth_provider() -> str:
    return os.getenv("GLRCHAIN_AUTH_PROVIDER", "local").strip().lower()


def _jwt_secret() -> str:
    secret = os.getenv("SECRET_KEY")
    if not secret or len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this service.",
        )
    return secret


def _get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        project_id = os.getenv("FIREBASE_PROJECT_ID")
        if not project_id:
            raise RuntimeError("FIREBASE_PROJECT_ID is required for Firebase Authentication.")
        return firebase_admin.initialize_app(options={"projectId": project_id})


async def _verify_firebase_token(token: str) -> dict:
    """Verify an ID token from the Firebase client SDK using Google credentials."""
    app = _get_firebase_app()
    return await asyncio.to_thread(
        firebase_auth.verify_id_token,
        token,
        app=app,
        check_revoked=True,
    )


async def get_firebase_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if _auth_provider() != "firebase":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Firebase identity provisioning is not enabled.",
        )
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A Firebase bearer ID token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        decoded = await _verify_firebase_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The Firebase ID token is invalid, expired, or revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not isinstance(decoded.get("uid"), str) or not decoded["uid"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="The Firebase token has no user identity.")
    return decoded


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


@router.post("/provision", response_model=UserOut)
async def provision_firebase_user(
    profile: FirebaseProvision,
    identity: dict = Depends(get_firebase_identity),
    db: AsyncSession = Depends(get_db),
):
    """Create a normal GLRChain profile for an already verified Firebase user."""
    uid = identity["uid"]
    existing = await db.scalar(select(User).where(User.firebase_uid == uid))
    if existing is not None:
        return existing

    username_owner = await db.scalar(select(User.id).where(User.username == profile.username))
    if username_owner is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already in use.")

    user = User(
        username=profile.username,
        hashed_password=FIREBASE_MANAGED_PASSWORD_MARKER,
        firebase_uid=uid,
        role="user",
    )
    db.add(user)
    try:
        await db.flush()
        await append_audit_event(
            db,
            actor_user_id=user.id,
            action="user.firebase_provisioned",
            object_type="user",
            object_id=str(user.id),
            details={"role": "user", "identity_provider": "firebase"},
        )
        await db.commit()
        await db.refresh(user)
        return user
    except IntegrityError:
        await db.rollback()
        # Idempotent retry after a concurrent provision for the same Firebase UID.
        existing = await db.scalar(select(User).where(User.firebase_uid == uid))
        if existing is not None:
            return existing
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or Firebase identity is already registered.")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user_input: UserCreate, db: AsyncSession = Depends(get_db)):
    if _auth_provider() == "firebase":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password registration is disabled. Register through the configured Firebase client and call /auth/provision.",
        )

    existing = await db.scalar(select(User.id).where(User.username == user_input.username))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already registered.")

    # Public/local registration cannot set a role or Firebase UID.
    user = User(
        username=user_input.username,
        hashed_password=pwd_context.hash(user_input.password),
        role="user",
    )
    db.add(user)
    try:
        await db.flush()
        await append_audit_event(
            db,
            actor_user_id=user.id,
            action="user.registered",
            object_type="user",
            object_id=str(user.id),
            details={"role": "user", "identity_provider": "local"},
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already registered.")
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(user_input: UserLogin, db: AsyncSession = Depends(get_db)):
    if _auth_provider() == "firebase":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password login is disabled. Sign in through Firebase Authentication and send the Firebase ID token.",
        )

    user = await db.scalar(select(User).where(User.username == user_input.username))
    stored_hash = user.hashed_password if user is not None else DUMMY_PASSWORD_HASH
    try:
        verified, replacement_hash = pwd_context.verify_and_update(user_input.password, stored_hash)
    except (TypeError, ValueError):
        verified, replacement_hash = False, None

    if user is None or not verified or user.hashed_password == FIREBASE_MANAGED_PASSWORD_MARKER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Successful legacy bcrypt logins upgrade to Argon2id.
    if replacement_hash:
        user.hashed_password = replacement_hash
    await append_audit_event(
        db,
        actor_user_id=user.id,
        action="auth.login_succeeded",
        object_type="user",
        object_id=str(user.id),
        details={"identity_provider": "local"},
    )
    await db.commit()

    token = create_access_token(user)
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="A valid bearer token is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    if _auth_provider() == "firebase":
        try:
            decoded = await _verify_firebase_token(credentials.credentials)
        except Exception:
            raise unauthorized
        uid = decoded.get("uid")
        if not isinstance(uid, str) or not uid:
            raise unauthorized
        user = await db.scalar(select(User).where(User.firebase_uid == uid))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This verified Firebase identity has no GLRChain profile. Call /auth/provision first.",
            )
        return user

    try:
        payload = jwt.decode(credentials.credentials, _jwt_secret(), algorithms=[JWT_ALGORITHM])
        subject = payload.get("sub")
        user_id = int(subject)
    except (JWTError, TypeError, ValueError):
        raise unauthorized

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise unauthorized
    return user


def require_roles(*roles: str):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != "admin" and current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges.")
        return current_user

    return role_checker


@router.get("/me", response_model=UserOut)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
