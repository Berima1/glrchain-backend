import os
import logging
from fastapi import FastAPI, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from pydantic import BaseModel
from cryptography.fernet import Fernet
import aiofiles

# ======================================================
# CONFIG
# ======================================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./glrchain.db")

def get_secret_key():
    secret = os.getenv("SECRET_KEY")
    if not secret:
        # Generate a valid Fernet key if missing
        secret = Fernet.generate_key().decode()
        print("⚠️ WARNING: SECRET_KEY not set, generated a new one.")
    else:
        try:
            # Validate Fernet format
            Fernet(secret.encode())
        except Exception:
            print("⚠️ WARNING: Invalid SECRET_KEY, generating new valid key.")
            secret = Fernet.generate_key().decode()
    return secret

SECRET_KEY = get_secret_key()
cipher = Fernet(SECRET_KEY.encode())

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("glrchain")

app = FastAPI(
    title="GLRChain Backend",
    description="Backend API for GLRChain - Fighting galamsey with AI, Blockchain, and Encryption",
    version="1.0.0"
)
