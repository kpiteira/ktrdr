"""Integration tests for M2: Orphan Detection.

This test suite verifies the complete M2 orphan detection flow:
1. Create operation with worker claiming it
2. Simulate worker disappearance (remove from registry)
3. Wait for orphan detection (timeout simulation)
4. Verify operation marked FAILED
5. Verify error message is informative

Note: This uses simulated time advancement for fast feedback.
For real Docker-based tests, see tests/e2e/container/
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)
from ktrdr.api.models.workers import WorkerType
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.services.orphan_detector import OrphanOperationDetector
from ktrdr.api.services.worker_registry import WorkerRegistry


@pytest.fixture
def mock_repository():
    """Create a mock repository that stores operations in memory.

    This simulates the actual repository behavior for integration testing.
    """
    storage: dict[str, OperationInfo] = {}

    repo = AsyncMock()

    async def mock_create(operation: OperationInfo) -> OperationInfo:
        storage[operation.operation_id] = operation
        return operation

    async def mock_get(operation_id: str) -> OperationInfo | None:
        return storage.get(operation_id)

    async def mock_update(operation_id: str, **fields) -> OperationInfo | None:
        if operation_id not in storage:
            return None
        op = storage[operation_id]
        # Update fields on the stored operation
        for key, value in fields.items():
            if key == "status" and isinstance(value, str):
                value = OperationStatus(value)
            if hasattr(op, key):
                setattr(op, key, value)
        return op

    async def mock_list(
        status: str | None = None, worker_id: str | None = None
    ) -> list[OperationInfo]:
        results = list(storage.values())
        if status:
            results = [op for op in results if op.status.value == status]
        return results

    async def mock_delete(operation_id: str) -> bool:
        if operation_id in storage:
            del storage[operation_id]
            return True
        return False

    repo.create = AsyncMock(side_effect=mock_create)
    repo.get = AsyncMock(side_effect=mock_get)
    repo.update = AsyncMock(side_effect=mock_update)
    repo.list = AsyncMock(side_effect=mock_list)
    repo.delete = AsyncMock(side_effect=mock_delete)
    repo._storage = storage  # Expose for test inspection

    return repo


@pytest.fixture
def operations_service(mock_repository):
    """Create OperationsService with mock repository."""
    return OperationsService(repository=mock_repository)


@pytest.fixture
def worker_registry(operations_service):
    """Create WorkerRegistry connected to OperationsService."""
    registry = WorkerRegistry()
    registry.set_operations_service(operations_service)
    return registry


class TestM2OrphanDetectionIntegration:
    """Integration tests for M2: Orphan Detection."""

    @pytest.mark.asyncio
    async def test_orphan_detection_after_worker_disappearance(
        self, worker_registry, operations_service, mock_repository
    ):
        """Test that operations are marked FAILED when worker disappears.

        This is the core M2 integration test that verifies:
        1. Worker registers and claims an operation
        2. Worker is removed from registry (simulating crash)
        3. Orphan detector identifies the orphan
        4. After timeout, operation is marked FAILED
        """
        # Step 1: Register a worker
        await worker_registry.register_worker(
            worker_id="training-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://worker:5004",
        )

        # Step 2: Create an operation and assign to worker
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
        )

        # Mark as RUNNING (simulating what happens when operation starts)
        await mock_repository.update(
            operation.operation_id,
            status=OperationStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        # Worker claims the operation (mark_busy sets current_operation_id)
        worker_registry.mark_busy("training-worker-1", operation.operation_id)

        # Verify worker claims the operation
        worker = worker_registry.get_worker("training-worker-1")
        assert worker.current_operation_id == operation.operation_id

        # Step 3: Create orphan detector with short timeout for testing
        detector = OrphanOperationDetector(
            operations_service=operations_service,
            worker_registry=worker_registry,
            orphan_timeout_seconds=1,  # Short timeout for testing
            check_interval_seconds=0.1,  # Fast checks for testing
        )

        # First check - operation is not orphan (worker claims it)
        await detector._check_for_orphans()
        assert operation.operation_id not in detector._potential_orphans

        # Step 4: Simulate worker crash (remove from registry)
        worker_registry._workers.clear()

        # Check again - now operation is potential orphan
        await detector._check_for_orphans()
        assert operation.operation_id in detector._potential_orphans

        # Step 5: Wait for timeout and check again
        await asyncio.sleep(1.1)  # Just past 1 second timeout
        await detector._check_for_orphans()

        # Step 6: Verify operation is marked FAILED
        final_op = await operations_service.get_operation(operation.operation_id)
        assert final_op.status == OperationStatus.FAILED
        assert final_op.error_message is not None
        assert "no worker claimed it" in final_op.error_message.lower()

        # Verify no longer tracked as potential orphan
        assert operation.operation_id not in detector._potential_orphans

    @pytest.mark.asyncio
    async def test_worker_reclaiming_clears_potential_orphan(
        self, worker_registry, operations_service, mock_repository
    ):
        """Test that when a worker reclaims an operation, it's no longer an orphan.

        This tests the scenario where:
        1. Worker disappears (potential orphan detected)
        2. Worker re-registers before timeout
        3. Operation is no longer considered orphan
        """
        # Create and start an operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(symbol="AAPL", timeframe="1d"),
        )
        await mock_repository.update(
            operation.operation_id,
            status=OperationStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        # Create detector
        detector = OrphanOperationDetector(
            operations_service=operations_service,
            worker_registry=worker_registry,
            orphan_timeout_seconds=60,
            check_interval_seconds=0.1,
        )

        # Initially no workers - operation becomes potential orphan
        await detector._check_for_orphans()
        assert operation.operation_id in detector._potential_orphans

        # Worker registers and claims the operation
        await worker_registry.register_worker(
            worker_id="backtest-worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker:5003",
        )
        # mark_busy sets current_operation_id on the worker
        worker_registry.mark_busy("backtest-worker-1", operation.operation_id)

        # Check again - should remove from potential orphans
        await detector._check_for_orphans()
        assert operation.operation_id not in detector._potential_orphans

        # Operation should still be RUNNING (not marked FAILED)
        current_op = await operations_service.get_operation(operation.operation_id)
        assert current_op.status == OperationStatus.RUNNING

    @pytest.mark.asyncio
    async def test_backend_local_operations_ignored(
        self, worker_registry, operations_service, mock_repository
    ):
        """Test that backend-local operations are not flagged as orphans.

        Backend-local operations (like agent sessions) run in the backend process
        and are handled by StartupReconciliation, not the orphan detector.
        """
        # Create a backend-local operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(
                symbol="EURUSD",
                timeframe="1h",
            ),
            is_backend_local=True,
        )
        await mock_repository.update(
            operation.operation_id,
            status=OperationStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        # Create detector with short timeout
        detector = OrphanOperationDetector(
            operations_service=operations_service,
            worker_registry=worker_registry,
            orphan_timeout_seconds=1,
            check_interval_seconds=0.1,
        )

        # No workers, but operation is backend-local
        await detector._check_for_orphans()

        # Should NOT be tracked as potential orphan
        assert operation.operation_id not in detector._potential_orphans

        # Wait past timeout
        await asyncio.sleep(1.1)
        await detector._check_for_orphans()

        # Should still be RUNNING (not FAILED)
        final_op = await operations_service.get_operation(operation.operation_id)
        assert final_op.status == OperationStatus.RUNNING

    @pytest.mark.asyncio
    async def test_multiple_orphans_handled_independently(
        self, worker_registry, operations_service, mock_repository
    ):
        """Test that multiple orphan operations are detected independently.

        Each orphan has its own first-seen timestamp and is handled separately.
        """
        # Create two operations
        op1 = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
        )
        await mock_repository.update(
            op1.operation_id,
            status=OperationStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        op2 = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(symbol="GBPUSD", timeframe="4h"),
        )
        await mock_repository.update(
            op2.operation_id,
            status=OperationStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        # Create detector
        detector = OrphanOperationDetector(
            operations_service=operations_service,
            worker_registry=worker_registry,
            orphan_timeout_seconds=1,
            check_interval_seconds=0.1,
        )

        # First check - both become potential orphans
        await detector._check_for_orphans()
        assert op1.operation_id in detector._potential_orphans
        assert op2.operation_id in detector._potential_orphans

        # Wait for timeout on first operation only by manipulating first_seen
        detector._potential_orphans[op1.operation_id] = datetime.now(
            timezone.utc
        ) - timedelta(seconds=2)

        # Check - op1 should be marked FAILED, op2 still tracked
        await detector._check_for_orphans()

        final_op1 = await operations_service.get_operation(op1.operation_id)
        final_op2 = await operations_service.get_operation(op2.operation_id)

        assert final_op1.status == OperationStatus.FAILED
        assert final_op2.status == OperationStatus.RUNNING
        assert op1.operation_id not in detector._potential_orphans
        assert op2.operation_id in detector._potential_orphans

    @pytest.mark.asyncio
    async def test_error_message_is_informative(
        self, worker_registry, operations_service, mock_repository
    ):
        """Test that the error message clearly explains the orphan failure."""
        # Create a running operation with no workers
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
        )
        await mock_repository.update(
            operation.operation_id,
            status=OperationStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        # Create detector with immediate timeout
        detector = OrphanOperationDetector(
            operations_service=operations_service,
            worker_registry=worker_registry,
            orphan_timeout_seconds=0,  # Immediate timeout
            check_interval_seconds=0.1,
        )

        # First check - starts tracking
        await detector._check_for_orphans()

        # Second check - should fail (timeout is 0)
        await detector._check_for_orphans()

        # Check error message
        final_op = await operations_service.get_operation(operation.operation_id)
        assert final_op.status == OperationStatus.FAILED
        assert final_op.error_message is not None

        # Error message should explain what happened
        error_msg = final_op.error_message.lower()
        assert "running" in error_msg or "operation" in error_msg
        assert "worker" in error_msg
        assert "claimed" in error_msg


class TestM2OrphanDetectorWithBackgroundLoop:
    """Integration tests using the actual background detection loop."""

    @pytest.mark.asyncio
    async def test_full_detection_loop_integration(
        self, worker_registry, operations_service, mock_repository
    ):
        """Test the full detection loop running as background task.

        This tests the integrated behavior with the actual asyncio task,
        rather than calling _check_for_orphans directly.
        """
        # Create a running operation with no workers
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
        )
        await mock_repository.update(
            operation.operation_id,
            status=OperationStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        # Create and start detector with very short intervals
        detector = OrphanOperationDetector(
            operations_service=operations_service,
            worker_registry=worker_registry,
            orphan_timeout_seconds=0.2,  # 200ms timeout
            check_interval_seconds=0.1,  # 100ms check interval
        )

        await detector.start()

        try:
            # Wait for detection to occur (timeout + some buffer)
            await asyncio.sleep(0.5)

            # Verify operation was marked FAILED
            final_op = await operations_service.get_operation(operation.operation_id)
            assert final_op.status == OperationStatus.FAILED

            # Verify detector status reflects activity
            status = detector.get_status()
            assert status["running"] is True
            assert status["last_check"] is not None
        finally:
            await detector.stop()

    @pytest.mark.asyncio
    async def test_detector_start_stop_lifecycle(
        self, worker_registry, operations_service, mock_repository
    ):
        """Test that detector starts and stops cleanly."""
        detector = OrphanOperationDetector(
            operations_service=operations_service,
            worker_registry=worker_registry,
            orphan_timeout_seconds=60,
            check_interval_seconds=1,
        )

        # Initially not running
        assert detector.get_status()["running"] is False

        # Start and verify running
        await detector.start()
        assert detector.get_status()["running"] is True

        # Stop and verify not running
        await detector.stop()
        assert detector.get_status()["running"] is False

        # Should be safe to stop again
        await detector.stop()
        assert detector.get_status()["running"] is False
