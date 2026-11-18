"""
Async SQLAlchemy engine + session factory.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_engine_kwargs = dict(echo=settings.DEBUG, pool_pre_ping=True)
if not _is_sqlite:
    _engine_kwargs.update(pool_size=10, max_overflow=20)

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncSession:
    """FastAPI / general dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables (dev/test). Use Alembic migrations in production."""
    from database.models import Base  # noqa: PLC0415 — avoid circular at module level

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
