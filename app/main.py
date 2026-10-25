import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text

from app.database import engine
from app.models import Base
from app.routes import admin, auth, reports

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("glrchain")


@asynccontextmanager
async def lifespan(_app: FastAPI):
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
