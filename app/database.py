import os
from collections.abc import AsyncIterator, Mapping

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def normalize_database_url(url: str) -> str:
    """Normalize managed PostgreSQL URLs to the async SQLAlchemy driver."""
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


def database_url_from_env(env: Mapping[str, str] | None = None) -> str:
    """Allow SQLite only for development/test; never silently use it in production."""
    source = os.environ if env is None else env
    configured_url = source.get("DATABASE_URL")
    app_env = source.get("APP_ENV", "development").strip().lower()

    if not configured_url and app_env in {"prod", "production"}:
        raise RuntimeError(
            "DATABASE_URL is required when APP_ENV is production; "
            "refusing to start against a local SQLite file."
        )

    if not configured_url:
        return "sqlite+aiosqlite:///./glrchain.db"
    return normalize_database_url(configured_url)


DATABASE_URL = database_url_from_env()
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
