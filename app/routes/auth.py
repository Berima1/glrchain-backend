import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from passlib.context import CryptContext
from jose import jwt, JWTError

from app.schemas import UserCreate, Token, TokenData, UserOut
from app.models import User
from app.database import get_db  # your get_db yields AsyncSession

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_replace_me")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MIN_MINUTES", "720"))

router = APIRouter()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    now = datetime.utcnow()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/register", response_model=UserOut)
async def register(u: UserCreate, db: AsyncSession = Depends(get_db)):
    # check username
    q = await db.execute(select(User).filter(User.username == u.username))
    existing = q.scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed = get_password_hash(u.password)
    new = User(username=u.username, hashed_password=hashed)
    db.add(new)
    await db.commit()
    await db.refresh(new)
    return UserOut(id=new.id, username=new.username)

@router.post("/login", response_model=Token)
async def login(form: UserCreate, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(User).filter(User.username == form.username))
    user = q.scalars().first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access_token = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

# dependency to get current user from token
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        token_data = TokenData(sub=sub)
    except JWTError:
        raise credentials_exception
    # fetch user by id
    q = await db.execute(select(User).filter(User.id == int(token_data.sub)))
    user = q.scalars().first()
    if user is None:
        raise credentials_exception
    return user

# role-required helper
def require_role(role: str):
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user.role != role and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return current_user
    return role_checker
