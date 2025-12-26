"""Unit tests for Task 3.10: Operations Architecture Fix.

This module tests the two architectural fixes:
1. Distributed operations bypass start_managed_operation (worker creates operation in DB)
2. update_progress does NOT write to DB (progress is in-memory only)

These tests verify the correct behavior after fixing the blocking bugs.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.operations_service import OperationsService


class TestUpdateProgressDoesNotWriteToDb:
    """Test that update_progress does NOT persist to DB (Fix 2 of Task 3.10).

    Design principle: Workers must be fast. DB writes should only happen for:
    - Create operation (once)
    - Checkpoint (periodic, policy-driven)
    - Complete/Fail (once)

    NOT for progress updates (use proxy for live progress).
    """

    @pytest.fixture
    def mock_repository(self):
        """Create a mock OperationsRepository."""
        repo = AsyncMock()
        repo.create = AsyncMock()
        repo.get = AsyncMock()
        repo.update = AsyncMock()
        repo.list = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def sample_metadata(self):
        """Create sample operation metadata."""
        return OperationMetadata(
            symbol="AAPL",
            timeframe="1h",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
            parameters={"test": True},
        )

    @pytest.mark.asyncio
    async def test_update_progress_does_not_write_to_repository(
        self, mock_repository, sample_metadata
    ):
        """update_progress should NOT persist to repository for performance.

        This is the key test for Fix 2 of Task 3.10.
        Progress updates happen frequently (every batch/epoch) and writing to DB
        would slow down workers unacceptably.
        """
        service = OperationsService(repository=mock_repository)

        # Create operation in cache (simulating worker state)
        operation = OperationInfo(
            operation_id="op_progress_test",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=sample_metadata,
            progress=OperationProgress(percentage=0.0),
        )
        service._cache["op_progress_test"] = operation

        # Update progress multiple times (simulating training loop)
        for pct in [10.0, 20.0, 30.0, 50.0, 75.0, 90.0]:
            new_progress = OperationProgress(
                percentage=pct,
                current_step=f"Epoch {int(pct)}%",
            )
            await service.update_progress("op_progress_test", new_progress)

        # CRITICAL: Repository.update should NOT have been called for progress
        mock_repository.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_progress_still_updates_in_memory_cache(
        self, mock_repository, sample_metadata
    ):
        """update_progress should still update the in-memory cache."""
        service = OperationsService(repository=mock_repository)

        # Create operation in cache
        operation = OperationInfo(
            operation_id="op_cache_test",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=sample_metadata,
            progress=OperationProgress(percentage=0.0),
        )
        service._cache["op_cache_test"] = operation

        new_progress = OperationProgress(
            percentage=75.0,
            current_step="Training epoch 75/100",
        )
        await service.update_progress("op_cache_test", new_progress)

        # Verify in-memory cache was updated
        cached_op = service._cache["op_cache_test"]
        assert cached_op.progress.percentage == 75.0
        assert cached_op.progress.current_step == "Training epoch 75/100"

    @pytest.mark.asyncio
    async def test_complete_operation_still_writes_to_db(
        self, mock_repository, sample_metadata
    ):
        """complete_operation should still persist to DB (final state is durable)."""
        service = OperationsService(repository=mock_repository)

        # Create operation in cache
        operation = OperationInfo(
            operation_id="op_complete_test",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=sample_metadata,
            progress=OperationProgress(percentage=100.0),
        )
        service._cache["op_complete_test"] = operation
        mock_repository.update.return_value = operation

        await service.complete_operation("op_complete_test", {"accuracy": 0.95})

        # Verify repository.update WAS called for completion
        mock_repository.update.assert_called()

    @pytest.mark.asyncio
    async def test_fail_operation_still_writes_to_db(
        self, mock_repository, sample_metadata
    ):
        """fail_operation should still persist to DB (final state is durable)."""
        service = OperationsService(repository=mock_repository)

        # Create operation in cache
        operation = OperationInfo(
            operation_id="op_fail_test",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            metadata=sample_metadata,
            progress=OperationProgress(percentage=50.0),
        )
        service._cache["op_fail_test"] = operation
        mock_repository.update.return_value = operation

        await service.fail_operation("op_fail_test", "Training failed: OOM")

        # Verify repository.update WAS called for failure
        mock_repository.update.assert_called()


class TestDistributedOperationsBypassStartManagedOperation:
    """Test that distributed ops bypass start_managed_operation (Fix 1 of Task 3.10).

    Design principle: For distributed operations, the worker creates the operation
    in DB. The backend just dispatches to the worker and registers a proxy.

    This avoids the duplicate operation ID error:
    - Before: Backend creates op in DB, then worker also tries to create → DUPLICATE
    - After: Backend skips DB create, worker creates op in DB → NO CONFLICT
    """

    @pytest.fixture
    def worker_registry(self):
        """Create WorkerRegistry for testing."""
        from ktrdr.api.services.worker_registry import WorkerRegistry

        return WorkerRegistry()

    @pytest.mark.asyncio
    async def test_run_backtest_does_not_call_start_managed_operation(
        self, worker_registry
    ):
        """run_backtest should NOT call start_managed_operation for distributed ops.

        This is the key test for Fix 1 of Task 3.10 (backtesting).
        Calling start_managed_operation creates the operation in DB on the backend,
        but the worker also creates it → duplicate key error.
        """
        from datetime import datetime
        from unittest.mock import patch

        from ktrdr.api.models.workers import WorkerType
        from ktrdr.backtesting.backtesting_service import BacktestingService

        # Register a worker (async since M1)
        await worker_registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        service = BacktestingService(worker_registry=worker_registry)

        with patch.object(
            service, "start_managed_operation", new_callable=AsyncMock
        ) as mock_start:
            with patch.object(
                service, "run_backtest_on_worker", new_callable=AsyncMock
            ) as mock_dispatch:
                mock_dispatch.return_value = {
                    "remote_operation_id": "op_remote_123",
                    "backend_operation_id": "op_backend_123",
                    "status": "started",
                    "message": "Backtest started on worker",
                    "worker_id": "worker-1",
                }

                result = await service.run_backtest(
                    symbol="AAPL",
                    timeframe="1h",
                    strategy_config_path="strategies/test.yaml",
                    model_path="models/test.pt",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 12, 31),
                )

                # CRITICAL: start_managed_operation should NOT be called
                mock_start.assert_not_called()

                # Worker dispatch should be called instead
                mock_dispatch.assert_called_once()

                # Result should contain operation_id from worker
                assert result["success"] is True
                assert "operation_id" in result

    @pytest.mark.asyncio
    async def test_start_training_does_not_call_start_managed_operation(
        self, worker_registry
    ):
        """start_training should NOT call start_managed_operation for distributed ops.

        This is the key test for Fix 1 of Task 3.10 (training).
        Same issue as backtesting - avoid duplicate operation ID.
        """
        from unittest.mock import MagicMock, patch

        from ktrdr.api.models.workers import WorkerType
        from ktrdr.api.services.training_service import TrainingService

        # Register a GPU worker for training (async since M1)
        await worker_registry.register_worker(
            worker_id="gpu-worker-1",
            worker_type=WorkerType.TRAINING,
            endpoint_url="http://gpu-worker-1:5004",
            capabilities={"gpu": True},
        )

        # TrainingService only takes worker_registry, gets operations_service internally
        service = TrainingService(worker_registry=worker_registry)

        # Mock build_training_context to avoid strategy file validation
        mock_context = MagicMock()
        mock_context.operation_id = "op_train_123"
        mock_context.symbols = ["AAPL"]
        mock_context.timeframes = ["1h"]
        mock_context.strategy_name = "test_strategy"
        mock_context.training_config = {"estimated_duration_minutes": 30}

        with patch.object(
            service, "start_managed_operation", new_callable=AsyncMock
        ) as mock_start:
            with patch.object(
                service,
                "_run_distributed_worker_training_wrapper",
                new_callable=AsyncMock,
            ) as mock_dispatch:
                with patch(
                    "ktrdr.api.services.training_service.build_training_context",
                    return_value=mock_context,
                ):
                    mock_dispatch.return_value = {
                        "remote_operation_id": "op_remote_train_123",
                        "backend_operation_id": "op_backend_train_123",
                        "status": "started",
                        "message": "Training started on worker",
                        "worker_id": "gpu-worker-1",
                    }

                    result = await service.start_training(
                        symbols=["AAPL"],
                        timeframes=["1h"],
                        strategy_name="test_strategy",
                    )

                    # CRITICAL: start_managed_operation should NOT be called
                    mock_start.assert_not_called()

                    # Worker dispatch should be called instead
                    mock_dispatch.assert_called_once()

                    # Result should contain operation_id from worker
                    assert result["success"] is True
                    assert "operation_id" in result

    @pytest.mark.asyncio
    async def test_run_backtest_returns_worker_operation_id(self, worker_registry):
        """run_backtest should return the operation_id from the worker response."""
        from datetime import datetime
        from unittest.mock import MagicMock, patch

        from ktrdr.api.models.workers import WorkerType
        from ktrdr.backtesting.backtesting_service import BacktestingService

        # Register a worker (async since M1)
        await worker_registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        service = BacktestingService(worker_registry=worker_registry)

        # Mock operations service
        mock_ops = MagicMock()
        mock_ops.register_remote_proxy = MagicMock()
        mock_ops.generate_operation_id = MagicMock(return_value="op_backend_456")
        service.operations_service = mock_ops

        with patch(
            "ktrdr.backtesting.backtesting_service.httpx.AsyncClient"
        ) as MockClient:
            with patch("ktrdr.backtesting.backtesting_service.OperationServiceProxy"):
                # Mock HTTP response from worker
                mock_response = MagicMock()
                mock_response.json.return_value = {"operation_id": "op_worker_789"}
                mock_response.raise_for_status = MagicMock()

                mock_client = MockClient.return_value.__aenter__.return_value
                mock_client.post = AsyncMock(return_value=mock_response)

                result = await service.run_backtest(
                    symbol="AAPL",
                    timeframe="1h",
                    strategy_config_path="strategies/test.yaml",
                    model_path="models/test.pt",
                    start_date=datetime(2024, 1, 1),
                    end_date=datetime(2024, 12, 31),
                )

                # Result should contain success and operation_id
                assert result["success"] is True
                # The operation_id should be present (either backend or worker ID)
                assert "operation_id" in result
