from fastapi import APIRouter, HTTPException
from app.schemas import UserCreate, Token
from passlib.context import CryptContext
import os, jwt, datetime

router = APIRouter()
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
SECRET_KEY = os.getenv('SECRET_KEY','dev-secret')
ALGORITHM = 'HS256'

# simple in-memory users for demo only
users = {}

@router.post('/register')
async def register(u: UserCreate):
    if u.email in users:
        raise HTTPException(status_code=400, detail='User exists')
    hashed = pwd_context.hash(u.password)
    users[u.email] = {'name': u.name, 'password': hashed, 'role': 'user'}
    return {'msg':'user created'}

@router.post('/login', response_model=Token)
async def login(u: UserCreate):
    user = users.get(u.email)
    if not user or not pwd_context.verify(u.password, user['password']):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    payload = {'sub': u.email, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=12)}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return Token(access_token=token)
