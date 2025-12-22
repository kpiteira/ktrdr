"""Integration tests that verify actual database persistence.

These tests query the database DIRECTLY to verify that operations
are actually persisted, not just cached in memory.

This catches bugs where the API returns success but nothing is written to DB.
"""

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from ktrdr.api.models.db.operations import OperationRecord
from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.operations_service import get_operations_service

# Skip all tests if DB not configured
pytestmark = pytest.mark.skipif(
    not os.getenv("DB_HOST"),
    reason="DB_HOST not configured - skipping DB integration tests",
)


def _get_database_url() -> str:
    """Construct database URL for tests."""
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "ktrdr")
    user = os.getenv("DB_USER", "ktrdr")
    password = os.getenv("DB_PASSWORD", "localdev")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


@pytest.fixture
def unique_operation_id():
    """Generate a unique operation ID for test isolation."""
    return f"op_test_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def db_session():
    """Create a fresh database session for this test."""
    engine = create_async_engine(_get_database_url(), echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def cleanup_operation_id(unique_operation_id, db_session):
    """Provide operation ID and cleanup after test."""
    yield unique_operation_id

    # Cleanup: delete test operation
    stmt = select(OperationRecord).where(
        OperationRecord.operation_id == unique_operation_id
    )
    result = await db_session.execute(stmt)
    record = result.scalar_one_or_none()
    if record:
        await db_session.delete(record)
        await db_session.commit()


class TestOperationPersistence:
    """Tests that verify operations actually persist to the database."""

    @pytest.mark.asyncio
    async def test_create_operation_persists_to_db(
        self, db_session, cleanup_operation_id
    ):
        """Creating an operation via service should write to database.

        This is the test that would have caught the M1 persistence bug.
        """
        op_id = cleanup_operation_id
        service = get_operations_service()

        # Create operation via service
        metadata = OperationMetadata(symbol="AAPL", timeframe="1h")
        operation = await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=metadata,
            operation_id=op_id,
        )

        assert operation.operation_id == op_id

        # CRITICAL: Query database DIRECTLY to verify persistence
        stmt = select(OperationRecord).where(OperationRecord.operation_id == op_id)
        result = await db_session.execute(stmt)
        record = result.scalar_one_or_none()

        # This assertion would have caught the bug!
        assert record is not None, (
            f"Operation {op_id} not found in database! "
            "Service returned success but nothing was persisted. "
            "Check that OperationsService has a repository injected."
        )

        assert record.operation_type == "training"
        assert record.status == "pending"

    @pytest.mark.asyncio
    async def test_update_operation_persists_to_db(
        self, db_session, cleanup_operation_id
    ):
        """Updating an operation should persist changes to database."""
        op_id = cleanup_operation_id
        service = get_operations_service()

        # Create operation
        metadata = OperationMetadata(symbol="AAPL", timeframe="1h")
        await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=metadata,
            operation_id=op_id,
        )

        # Update status via service
        await service.update_operation_status(op_id, OperationStatus.RUNNING)

        # Verify in database DIRECTLY
        stmt = select(OperationRecord).where(OperationRecord.operation_id == op_id)
        result = await db_session.execute(stmt)
        record = result.scalar_one_or_none()

        assert record is not None
        assert record.status == "running", (
            f"Expected status 'running', got '{record.status}'. "
            "Update may not be persisting to database."
        )

    @pytest.mark.asyncio
    async def test_operation_survives_cache_clear(
        self, db_session, cleanup_operation_id
    ):
        """Operations should be retrievable even after cache is cleared.

        This simulates what happens after a backend restart.
        """
        op_id = cleanup_operation_id
        service = get_operations_service()

        # Create operation
        metadata = OperationMetadata(symbol="AAPL", timeframe="1h")
        await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=metadata,
            operation_id=op_id,
        )

        # Clear the in-memory cache (simulate restart)
        service._cache.clear()

        # Should still be retrievable (from DB)
        operation = await service.get_operation(op_id)

        assert operation is not None, (
            f"Operation {op_id} not found after cache clear! "
            "This means the operation was only in memory, not in database."
        )
        assert operation.operation_id == op_id


class TestDatabaseConnectivity:
    """Tests that verify database connectivity is working."""

    @pytest.mark.asyncio
    async def test_database_is_accessible(self, db_session):
        """Verify we can connect to and query the database."""
        result = await db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_operations_table_exists(self, db_session):
        """Verify the operations table exists."""
        # Query that will fail if table doesn't exist
        stmt = select(OperationRecord).limit(1)
        result = await db_session.execute(stmt)
        # Should not raise - table exists
        result.scalars().all()  # Consume result

    @pytest.mark.asyncio
    async def test_can_write_and_read_operation(self, db_session, unique_operation_id):
        """Verify basic write/read cycle works at DB level."""
        # Write directly to DB
        record = OperationRecord(
            operation_id=unique_operation_id,
            operation_type="training",
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata_={"symbol": "TEST"},
        )
        db_session.add(record)
        await db_session.commit()

        # Read back
        stmt = select(OperationRecord).where(
            OperationRecord.operation_id == unique_operation_id
        )
        result = await db_session.execute(stmt)
        fetched = result.scalar_one_or_none()

        assert fetched is not None
        assert fetched.operation_id == unique_operation_id

        # Cleanup
        await db_session.delete(fetched)
        await db_session.commit()
