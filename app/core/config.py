"""Validated environment configuration for GLRChain."""
import os

from app.database import database_url_from_env

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
DATABASE_URL = database_url_from_env()
SECRET_KEY = os.getenv("SECRET_KEY")
REPORT_ENCRYPTION_KEY = os.getenv("REPORT_ENCRYPTION_KEY")
LEGACY_REPORT_ENCRYPTION_KEY = os.getenv("LEGACY_REPORT_ENCRYPTION_KEY")
EVIDENCE_BUCKET = os.getenv("GLRCHAIN_EVIDENCE_BUCKET")
