"""M1 Direct Database Persistence Tests.

These tests verify that operations actually persist to PostgreSQL by
querying the database directly, not through the service layer.

This catches bugs where:
- Service works but DB writes are skipped
- Repository is not injected
- Transactions aren't committed

See: docs/architecture/checkpoint/M1_TEST_GAP_ANALYSIS.md
"""

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text

from ktrdr.api.database import get_session
from ktrdr.api.models.db.operations import OperationRecord
from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.services.operations_service import get_operations_service


class TestDatabasePersistence:
    """Verify operations actually persist to PostgreSQL."""

    @pytest.mark.asyncio
    async def test_operation_persists_to_database(self):
        """CRITICAL: Create operation via service, verify in DB directly.

        This is the test that would have caught the original bug where
        get_operations_service() didn't inject the repository.
        """
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB test")

        # 1. Create operation via service
        service = get_operations_service()
        operation = await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="TESTPERSIST", timeframe="1h"),
        )
        operation_id = operation.operation_id

        # 2. Query DB directly (NOT through service)
        async with get_session() as session:
            result = await session.execute(
                select(OperationRecord).where(
                    OperationRecord.operation_id == operation_id
                )
            )
            record = result.scalar_one_or_none()

        # 3. Verify - this would FAIL if repository not injected
        assert record is not None, (
            f"Operation {operation_id} not found in database! "
            "Repository may not be injected in get_operations_service()"
        )
        assert record.operation_type == "training"
        assert record.status.upper() == "PENDING"
        assert record.metadata_["symbol"] == "TESTPERSIST"

    @pytest.mark.asyncio
    async def test_operation_update_persists_to_database(self):
        """Verify operation status updates persist to DB."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB test")

        # 1. Create and start operation
        service = get_operations_service()
        operation = await service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(symbol="TESTUPDATEPERSIST", timeframe="4h"),
        )
        operation_id = operation.operation_id

        # Create a mock task for start_operation
        import asyncio
        from unittest.mock import MagicMock

        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.done.return_value = False
        mock_task.cancelled.return_value = False

        await service.start_operation(operation_id, mock_task)

        # 2. Query DB directly
        async with get_session() as session:
            result = await session.execute(
                select(OperationRecord).where(
                    OperationRecord.operation_id == operation_id
                )
            )
            record = result.scalar_one_or_none()

        # 3. Verify status update persisted
        assert record is not None
        assert record.status.upper() == "RUNNING", (
            "Status update did not persist to database! "
            "Check that OperationsService updates call repository.update()"
        )
        assert record.started_at is not None

    @pytest.mark.asyncio
    async def test_operation_survives_service_restart(self):
        """CRITICAL: Operations should survive service restart (cache clear).

        This simulates backend restart by clearing the service's in-memory
        cache and verifying data is reloaded from database.
        """
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB test")

        # 1. Create operation
        service = get_operations_service()
        operation = await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="TESTRESTART", timeframe="1d"),
        )
        operation_id = operation.operation_id

        # 2. Simulate restart: clear in-memory cache
        service._cache.clear()

        # 3. Retrieve operation (should reload from DB)
        retrieved = await service.get_operation(operation_id)

        # 4. Verify operation still exists
        assert retrieved is not None, (
            f"Operation {operation_id} lost after cache clear! "
            "Data should reload from database (read-through cache)"
        )
        assert retrieved.operation_id == operation_id
        assert retrieved.metadata.symbol == "TESTRESTART"


class TestReconciliationPersistence:
    """Verify reconciliation updates actually persist to database."""

    @pytest.mark.asyncio
    async def test_startup_reconciliation_updates_database(self):
        """Verify startup reconciliation writes to DB, not just cache (Task 1.8)."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB test")

        from ktrdr.api.database import get_session_factory
        from ktrdr.api.repositories.operations_repository import OperationsRepository
        from ktrdr.api.services.startup_reconciliation import StartupReconciliation

        # 1. Create a RUNNING operation directly in DB
        operation_id = f"op_reconcile_test_{uuid.uuid4().hex[:8]}"
        async with get_session() as session:
            record = OperationRecord(
                operation_id=operation_id,
                operation_type="training",
                status="RUNNING",
                worker_id="test-worker",
                is_backend_local=True,
                created_at=datetime.now(timezone.utc),
                metadata_={"symbol": "RECONCILETEST", "timeframe": "1h"},
            )
            session.add(record)
            await session.commit()

        # 2. Run startup reconciliation
        session_factory = get_session_factory()
        repository = OperationsRepository(session_factory)
        reconciliation = StartupReconciliation(repository)
        result = await reconciliation.reconcile()

        # 3. Verify DB was updated (not just cache)
        async with get_session() as session:
            updated = await session.execute(
                select(OperationRecord).where(
                    OperationRecord.operation_id == operation_id
                )
            )
            record = updated.scalar_one_or_none()

        # 4. Backend-local RUNNING op should be marked FAILED
        assert record is not None
        assert record.status.upper() == "FAILED", (
            "Startup reconciliation did not update database! "
            "Backend-local RUNNING operation should be marked FAILED"
        )
        assert "Backend restarted" in (record.error_message or "")

    @pytest.mark.asyncio
    async def test_worker_reconciliation_updates_database(self):
        """Verify worker re-registration reconciliation persists to DB (Task 1.5)."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB test")

        from ktrdr.api.models.workers import CompletedOperationReport, WorkerType
        from ktrdr.api.services.operations_service import get_operations_service
        from ktrdr.api.services.worker_registry import WorkerRegistry

        # 1. Create a RUNNING operation in DB
        service = get_operations_service()
        operation = await service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="WORKERRECONCILE", timeframe="15m"),
        )
        operation_id = operation.operation_id

        import asyncio
        from unittest.mock import MagicMock

        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.done.return_value = False
        await service.start_operation(operation_id, mock_task)

        # 2. Clear cache to simulate restart
        service._cache.clear()

        # 3. Worker re-registers with completed operation
        registry = WorkerRegistry()
        registry.set_operations_service(service)

        completed_report = CompletedOperationReport(
            operation_id=operation_id,
            status="COMPLETED",
            result={"test": "result"},
            completed_at=datetime.now(timezone.utc),
        )

        await registry.register_worker(
            worker_id="test-worker-reconcile",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://test:5000",
            completed_operations=[completed_report],
        )

        # 4. Query DB directly to verify reconciliation persisted
        async with get_session() as session:
            result = await session.execute(
                select(OperationRecord).where(
                    OperationRecord.operation_id == operation_id
                )
            )
            record = result.scalar_one_or_none()

        # 5. Verify status was updated in DB, not just cache
        assert record is not None
        assert record.status.upper() == "COMPLETED", (
            "Worker reconciliation did not persist to database! "
            "Completed operation should be marked COMPLETED in DB"
        )


class TestDatabaseSchema:
    """Verify database schema is correct (Task 1.1)."""

    @pytest.mark.asyncio
    async def test_operations_table_exists(self):
        """Verify operations table exists with correct schema."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB test")

        async with get_session() as session:
            # Check table exists
            result = await session.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT FROM information_schema.tables "
                    "WHERE table_name = 'operations'"
                    ")"
                )
            )
            exists = result.scalar()

        assert exists, (
            "Operations table does not exist! "
            "Run: alembic upgrade head"
        )

    @pytest.mark.asyncio
    async def test_operations_table_has_required_columns(self):
        """Verify operations table has all required columns."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB test")

        required_columns = [
            "operation_id",
            "operation_type",
            "status",
            "worker_id",
            "is_backend_local",
            "created_at",
            "started_at",
            "completed_at",
            "metadata",  # Note: column name is "metadata", SQLAlchemy uses "metadata_"
            "result",
            "error_message",
            "reconciliation_status",
        ]

        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT column_name "
                    "FROM information_schema.columns "
                    "WHERE table_name = 'operations'"
                )
            )
            columns = [row[0] for row in result.fetchall()]

        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    @pytest.mark.asyncio
    async def test_can_query_operations_table(self):
        """Verify we can query the operations table (smoke test)."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB test")

        async with get_session() as session:
            # This should not raise
            result = await session.execute(
                text("SELECT COUNT(*) FROM operations")
            )
            count = result.scalar()

        # Just verify the query works (count can be 0 or more)
        assert count is not None


class TestServiceLogging:
    """Verify service initialization logging (Test #4 from gap analysis)."""

    def test_startup_logs_persistence_mode(self):
        """Startup should log whether DB persistence is enabled."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB test")

        import logging

        # Set up logging capture
        logger = logging.getLogger("ktrdr.api.services.operations_service")
        original_level = logger.level
        logger.setLevel(logging.INFO)

        # Create a handler to capture logs
        import io

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)

        try:
            # Force re-initialization by clearing global
            import ktrdr.api.services.operations_service as ops_module

            ops_module._operations_service = None

            # Initialize service
            service = get_operations_service()

            # Verify log message indicates persistence
            log_text = log_stream.getvalue().lower()
            assert "database persistence" in log_text or "persistence" in log_text, (
                "Startup should log that database persistence is enabled. "
                "This helps diagnose configuration issues. "
                f"Got log: {log_text}"
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)
