from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def async_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


_engine = None
_factory = None


def session_factory():
    global _engine, _factory
    if _factory is None:
        url = get_settings().database_url
        if not url:
            raise RuntimeError("DATABASE_URL is not configured")
        _engine = create_async_engine(async_url(url), pool_pre_ping=True, pool_size=5, max_overflow=2)
        _factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _factory = None
