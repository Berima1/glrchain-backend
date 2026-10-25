import logging
import os
from contextlib import asynccontextmanager

from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine
from app.models import Base
from app.routes import admin, auth, reports

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("glrchain")


def validate_production_configuration() -> None:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env not in {"prod", "production"}:
        return

    jwt_secret = os.getenv("SECRET_KEY")
    if not jwt_secret or len(jwt_secret) < 32:
        raise RuntimeError("Production requires a persistent SECRET_KEY of at least 32 characters.")

    encryption_key = os.getenv("REPORT_ENCRYPTION_KEY")
    if not encryption_key:
        raise RuntimeError("Production requires REPORT_ENCRYPTION_KEY.")
    try:
        Fernet(encryption_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise RuntimeError("REPORT_ENCRYPTION_KEY must be a valid persistent Fernet key.") from exc

    if not os.getenv("GLRCHAIN_EVIDENCE_BUCKET"):
        raise RuntimeError("Production requires GLRCHAIN_EVIDENCE_BUCKET for private evidence storage.")

    if os.getenv("GLRCHAIN_AUTH_PROVIDER", "").strip().lower() != "firebase":
        raise RuntimeError("Production requires GLRCHAIN_AUTH_PROVIDER=firebase; local password auth is for controlled development only.")
    if not os.getenv("FIREBASE_PROJECT_ID"):
        raise RuntimeError("Production requires FIREBASE_PROJECT_ID for Firebase ID-token verification.")
    if not os.getenv("GLRCHAIN_ALLOWED_ORIGINS", "").strip():
        raise RuntimeError("Production requires GLRCHAIN_ALLOWED_ORIGINS with the approved frontend origin(s).")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_production_configuration()
    # Auto-creation is available only for explicit local/test use. Deployments must
    # apply reviewed Alembic migrations before the service is started.
    if os.getenv("GLRCHAIN_CREATE_SCHEMA_ON_STARTUP", "false").lower() == "true":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="GLRChain API",
    description=(
        "Ghana land and natural-resource reporting API. Satellite intelligence and "
        "blockchain evidence anchoring are not exposed as operational endpoints until "
        "their implementations are deployed and independently tested."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

# Browser access is restricted to explicit origins. Native clients are not governed by CORS,
# so every sensitive endpoint must still enforce server-side authentication and authorisation.
allowed_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "GLRCHAIN_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(reports.router, tags=["Reports and Evidence"])
app.include_router(admin.router, prefix="/admin", tags=["Administration"])


@app.get("/", tags=["Service"])
async def home():
    return {
        "service": "GLRChain API",
        "status": "running",
        "purpose": "Ghana land and natural-resource reporting",
        "api_docs": "/docs",
    }


@app.get("/health/live", tags=["Health"])
async def liveness():
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
async def readiness():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database readiness check failed.",
        )
    return {"status": "ready", "database": "ok"}
