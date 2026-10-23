from collections.abc import AsyncIterator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def async_url(url: str) -> str:
    parsed = make_url(url)
    if parsed.drivername in {"postgres", "postgresql"}:
        parsed = parsed.set(drivername="postgresql+asyncpg")
    return str(parsed)


def engine_options(url: str) -> tuple[str, dict]:
    """Translate libpq's sslmode query option into asyncpg's ssl connect arg."""
    parsed = make_url(async_url(url))
    query = dict(parsed.query)
    sslmode = query.pop("sslmode", None)
    parsed = parsed.set(query=query)
    options: dict = {}
    if sslmode:
        if sslmode in {"require", "verify-ca", "verify-full"}:
            options["connect_args"] = {"ssl": sslmode}
        elif sslmode == "prefer":
            options["connect_args"] = {"ssl": "prefer"}
        elif sslmode in {"disable", "allow"}:
            options["connect_args"] = {"ssl": False}
    return str(parsed), options


_engine = None
_factory = None


def session_factory():
    global _engine, _factory
    if _factory is None:
        url = get_settings().database_url
        if not url:
            raise RuntimeError("DATABASE_URL is not configured")
        normalized_url, options = engine_options(url)
        _engine = create_async_engine(
            normalized_url, pool_pre_ping=True, pool_size=5, max_overflow=2, **options
        )
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
