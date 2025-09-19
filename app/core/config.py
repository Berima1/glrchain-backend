# app/config.py
import os
from cryptography.fernet import Fernet

def load_secret_key():
    secret = os.getenv("SECRET_KEY")

    if not secret:
        # Generate one if not provided
        secret = Fernet.generate_key().decode()
        print("⚠️ WARNING: SECRET_KEY not set, generated a new one.")

    try:
        # Validate format
        Fernet(secret.encode())
    except Exception:
        print("⚠️ WARNING: Invalid SECRET_KEY, generating new valid key.")
        secret = Fernet.generate_key().decode()

    return secret

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./glrchain.db")
SECRET_KEY = load_secret_key()
