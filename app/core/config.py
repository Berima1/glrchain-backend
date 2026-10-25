"""Environment configuration helpers for GLRChain.

Secrets are deliberately not generated at runtime: replacing a key on restart can
make previously encrypted report descriptions unreadable.
"""
import os

from app.database import normalize_database_url

DATABASE_URL = normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./glrchain.db")
)
SECRET_KEY = os.getenv("SECRET_KEY")
REPORT_ENCRYPTION_KEY = os.getenv("REPORT_ENCRYPTION_KEY")
EVIDENCE_BUCKET = os.getenv("GLRCHAIN_EVIDENCE_BUCKET")
