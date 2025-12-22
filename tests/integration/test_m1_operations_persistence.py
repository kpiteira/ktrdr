"""Integration tests for M1: Operations Persistence + Worker Re-Registration.

This test suite verifies the complete M1 flow with simulated restart:
1. Create operation, verify in DB (via mock repository)
2. Simulate backend restart (clear in-memory state)
3. Worker re-registration with current_operation_id
4. Verify status synced correctly
5. Worker re-registration with completed_operations
6. Verify completed operation updated

Note: This uses simulated restart (clearing in-memory state) for fast feedback.
For real Docker restart tests, see tests/e2e/container/test_m1_backend_restart.py
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)
from ktrdr.api.models.workers import CompletedOperationReport, WorkerType
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.services.worker_registry import WorkerRegistry


@pytest.fixture
def mock_repository():
    """Create a mock repository that stores operations in memory."""
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


def create_mock_task() -> asyncio.Task:
    """Create a mock asyncio Task for testing start_operation."""

    # Create a simple coroutine that does nothing
    async def dummy_coro():
        pass

    # Create a task but don't actually run it
    task = MagicMock(spec=asyncio.Task)
    task.done.return_value = False
    task.cancelled.return_value = False
    return task


class TestM1OperationsPersistence:
    """Integration tests for M1: Operations Persistence."""

    @pytest.mark.asyncio
    async def test_operation_persisted_to_repository(
        self, operations_service, mock_repository
    ):
        """Test that operations are persisted to the repository."""
        # Create an operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
        )

        # Verify it was stored in the repository
        assert operation.operation_id in mock_repository._storage
        stored = mock_repository._storage[operation.operation_id]
        assert stored.operation_type == OperationType.TRAINING
        assert stored.status == OperationStatus.PENDING

    @pytest.mark.asyncio
    async def test_operation_survives_cache_clear(
        self, operations_service, mock_repository
    ):
        """Test that operations survive in-memory cache being cleared."""
        # Create an operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(symbol="AAPL", timeframe="1d"),
        )
        operation_id = operation.operation_id

        # Simulate restart: clear the in-memory cache
        operations_service._cache.clear()

        # Operation should still be retrievable (from repository)
        retrieved = await operations_service.get_operation(operation_id)
        assert retrieved is not None
        assert retrieved.operation_id == operation_id
        assert retrieved.operation_type == OperationType.BACKTESTING


class TestM1WorkerReRegistration:
    """Integration tests for M1: Worker Re-Registration with reconciliation."""

    @pytest.mark.asyncio
    async def test_reregistration_syncs_current_operation(
        self, worker_registry, operations_service, mock_repository
    ):
        """Test that re-registration syncs current operation status."""
        # 1. Create a RUNNING operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
        )
        await operations_service.start_operation(
            operation.operation_id, create_mock_task()
        )
        assert (
            await operations_service.get_operation(operation.operation_id)
        ).status == OperationStatus.RUNNING

        # 2. Simulate backend restart: clear in-memory state
        operations_service._cache.clear()
        worker_registry._workers.clear()

        # 3. Worker re-registers with current_operation_id
        result = await worker_registry.register_worker(
            worker_id="training-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://worker:5004",
            current_operation_id=operation.operation_id,
        )

        # 4. Verify operation status is reconciled
        reconciled = await operations_service.get_operation(operation.operation_id)
        assert reconciled is not None
        assert reconciled.status == OperationStatus.RUNNING

        # 5. No stop signal should be sent (operation should continue)
        assert operation.operation_id not in result.stop_operations

    @pytest.mark.asyncio
    async def test_reregistration_with_completed_operations(
        self, worker_registry, operations_service, mock_repository
    ):
        """Test that re-registration reconciles completed operations."""
        # 1. Create a RUNNING operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="GBPUSD", timeframe="4h"),
        )
        await operations_service.start_operation(
            operation.operation_id, create_mock_task()
        )

        # 2. Simulate backend restart
        operations_service._cache.clear()
        worker_registry._workers.clear()

        # 3. Worker re-registers reporting operation completed
        completed_report = CompletedOperationReport(
            operation_id=operation.operation_id,
            status="COMPLETED",
            result={"accuracy": 0.92, "model_path": "/models/test.pt"},
            completed_at=datetime.now(timezone.utc),
        )

        await worker_registry.register_worker(
            worker_id="training-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://worker:5004",
            completed_operations=[completed_report],
        )

        # 4. Verify operation is now COMPLETED in repository
        reconciled = await operations_service.get_operation(operation.operation_id)
        assert reconciled is not None
        assert reconciled.status == OperationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_reregistration_with_failed_operation(
        self, worker_registry, operations_service, mock_repository
    ):
        """Test that re-registration reconciles failed operations."""
        # 1. Create a RUNNING operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(symbol="USDJPY", timeframe="1h"),
        )
        await operations_service.start_operation(
            operation.operation_id, create_mock_task()
        )

        # 2. Simulate backend restart
        operations_service._cache.clear()
        worker_registry._workers.clear()

        # 3. Worker re-registers reporting operation failed
        failed_report = CompletedOperationReport(
            operation_id=operation.operation_id,
            status="FAILED",
            error_message="Out of memory during training",
            completed_at=datetime.now(timezone.utc),
        )

        await worker_registry.register_worker(
            worker_id="backtest-worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker:5003",
            completed_operations=[failed_report],
        )

        # 4. Verify operation is now FAILED
        reconciled = await operations_service.get_operation(operation.operation_id)
        assert reconciled is not None
        assert reconciled.status == OperationStatus.FAILED

    @pytest.mark.asyncio
    async def test_stop_signal_for_already_completed_operation(
        self, worker_registry, operations_service, mock_repository
    ):
        """Test that worker gets stop signal if operation is already completed in DB."""
        # 1. Create and complete an operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="AUDUSD", timeframe="1h"),
        )
        await operations_service.start_operation(
            operation.operation_id, create_mock_task()
        )
        await operations_service.complete_operation(
            operation.operation_id, result_summary={"status": "done"}
        )

        # 2. Simulate backend restart
        operations_service._cache.clear()
        worker_registry._workers.clear()

        # 3. Worker re-registers thinking it's still running the operation
        result = await worker_registry.register_worker(
            worker_id="training-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://worker:5004",
            current_operation_id=operation.operation_id,
        )

        # 4. Worker should receive stop signal
        assert operation.operation_id in result.stop_operations


class TestM1FullScenario:
    """Full M1 scenario test combining all components."""

    @pytest.mark.asyncio
    async def test_full_m1_flow(
        self, worker_registry, operations_service, mock_repository
    ):
        """
        Test the complete M1 flow:
        1. Worker registers
        2. Operation created and assigned to worker
        3. Backend "restarts" (cache cleared)
        4. Worker re-registers with operation state
        5. Operation state is reconciled
        """
        # Step 1: Worker registers
        await worker_registry.register_worker(
            worker_id="training-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://worker:5004",
        )
        assert worker_registry.get_worker("training-worker-1") is not None

        # Step 2: Create operation
        operation = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
        )
        await operations_service.start_operation(
            operation.operation_id, create_mock_task()
        )

        # Step 3: Simulate backend restart
        operations_service._cache.clear()
        worker_registry._workers.clear()

        # Verify in-memory state is cleared
        assert worker_registry.get_worker("training-worker-1") is None
        assert operation.operation_id not in operations_service._cache

        # But repository still has the operation
        assert operation.operation_id in mock_repository._storage

        # Step 4: Worker re-registers with current operation
        result = await worker_registry.register_worker(
            worker_id="training-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://worker:5004",
            current_operation_id=operation.operation_id,
        )

        # Step 5: Verify reconciliation
        # - Worker is registered again
        assert worker_registry.get_worker("training-worker-1") is not None

        # - Operation is still RUNNING (reconciled from worker report)
        reconciled = await operations_service.get_operation(operation.operation_id)
        assert reconciled.status == OperationStatus.RUNNING

        # - No stop signal (operation should continue)
        assert len(result.stop_operations) == 0
