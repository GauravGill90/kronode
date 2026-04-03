"""Database engine — SQLite by default, PostgreSQL optional.

SQLite: zero config, creates ~/.kronode/kronode.db automatically
PostgreSQL: set DATABASE_URL env var or database.url in config.toml
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, StaticPool

_engine = None
_session_factory = None


class Base(DeclarativeBase):
    pass


def get_engine():
    global _engine
    if _engine is None:
        from kronode.core.config import get_settings
        url = get_settings().database_url

        if "sqlite" in url:
            # SQLite: use StaticPool for async (single connection)
            _engine = create_async_engine(
                url, echo=False,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            # PostgreSQL: NullPool for async worker compatibility
            _engine = create_async_engine(url, echo=False, poolclass=NullPool)

    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


def AsyncSessionLocal():
    """Get an async session. Use as: async with AsyncSessionLocal() as db:"""
    return get_session_factory()()


async def init_db():
    """Create all tables (for SQLite — skip Alembic)."""
    # Import all models so Base.metadata knows about them
    import kronode.models.convention
    import kronode.models.doc_chunk
    import kronode.models.issue_index
    import kronode.models.memory

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# For FastAPI dependency injection (if using HTTP mode)
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# Convenience alias
engine = property(lambda self: get_engine())
