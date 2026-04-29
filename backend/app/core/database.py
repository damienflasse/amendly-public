from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Convert postgres:// → postgresql+asyncpg:// for async driver
_url = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace(
    "postgres://", "postgresql+asyncpg://"
)

# pool_size / max_overflow are not supported by SQLite (used in tests).
_is_sqlite = _url.startswith("sqlite")
_engine_kwargs: dict = {"echo": False, "pool_pre_ping": not _is_sqlite}
if not _is_sqlite:
    _engine_kwargs.update({"pool_size": 10, "max_overflow": 20})

engine = create_async_engine(_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
