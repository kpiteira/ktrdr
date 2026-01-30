"""Database configuration and session management.

Provides async database session management for the API layer.
Uses DatabaseSettings from ktrdr.config for configuration.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ktrdr.config import get_db_settings
from ktrdr.logging import get_logger

logger = get_logger(__name__)


def get_database_url() -> str:
    """Get the async database connection URL.

    Uses DatabaseSettings which supports both new (KTRDR_DB_*) and
    deprecated (DB_*) environment variable names.

    Returns:
        PostgreSQL async connection URL (asyncpg driver).
    """
    return get_db_settings().url


# Global engine and session factory (lazily initialized)
_engine = None
_session_factory = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        settings = get_db_settings()
        _engine = create_async_engine(
            settings.url,
            echo=settings.echo,
            pool_pre_ping=True,
        )
        # Log connection info without sensitive data (host/port/db only)
        logger.info(
            f"Database engine created for: {settings.host}:{settings.port}/{settings.name}"
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session as an async context manager.

    Usage:
        async with get_session() as session:
            result = await session.execute(query)
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def close_database():
    """Close the database engine and cleanup resources."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        logger.info("Database engine closed")
        _engine = None
        _session_factory = None
