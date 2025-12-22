"""Database configuration and session management.

Provides async database session management for the API layer.
Uses the same environment variables as the Docker Compose setup.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ktrdr.logging import get_logger

logger = get_logger(__name__)


def get_database_url() -> str:
    """Construct database URL from environment variables.

    Uses the same environment variables as the Docker Compose setup:
    - DB_HOST (default: localhost)
    - DB_PORT (default: 5432)
    - DB_NAME (default: ktrdr)
    - DB_USER (default: ktrdr)
    - DB_PASSWORD (default: localdev)

    Returns:
        PostgreSQL async connection URL.
    """
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "ktrdr")
    user = os.getenv("DB_USER", "ktrdr")
    password = os.getenv("DB_PASSWORD", "localdev")

    # Use asyncpg driver for async support
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


# Global engine and session factory (lazily initialized)
_engine = None
_session_factory = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        database_url = get_database_url()
        _engine = create_async_engine(
            database_url,
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
            pool_pre_ping=True,
        )
        # Log connection info without sensitive data (host/port/db only)
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "ktrdr")
        logger.info(f"Database engine created for: {db_host}:{db_port}/{db_name}")
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
