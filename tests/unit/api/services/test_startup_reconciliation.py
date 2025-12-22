"""Unit tests for StartupReconciliation service.

Tests the backend startup reconciliation logic that marks RUNNING operations
as either PENDING_RECONCILIATION (for worker-based ops) or FAILED (for backend-local ops).
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
from ktrdr.api.services.startup_reconciliation import StartupReconciliation


def _create_operation(
    operation_id: str,
    status: OperationStatus = OperationStatus.RUNNING,
    is_backend_local: bool = False,
    worker_id: str | None = "worker-123",
) -> OperationInfo:
    """Create a test operation with the given parameters."""
    return OperationInfo(
        operation_id=operation_id,
        operation_type=OperationType.TRAINING,
        status=status,
        created_at=datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2024, 12, 21, 10, 1, 0, tzinfo=timezone.utc),
        progress=OperationProgress(
            percentage=45.0,
            current_step="Training epoch 45",
            steps_completed=45,
            steps_total=100,
        ),
        metadata=OperationMetadata(
            symbol="EURUSD",
            timeframe="1h",
            parameters={
                "is_backend_local": is_backend_local,
                "worker_id": worker_id,
            },
        ),
    )


@pytest.fixture
def mock_repository():
    """Create a mock OperationsRepository."""
    repo = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    repo.update = AsyncMock()
    return repo


class TestStartupReconciliation:
    """Test StartupReconciliation service (Task 1.8)."""

    @pytest.mark.asyncio
    async def test_reconcile_with_no_running_operations(self, mock_repository):
        """Reconcile should do nothing when no RUNNING operations exist."""
        mock_repository.list.return_value = []

        reconciliation = StartupReconciliation(repository=mock_repository)
        result = await reconciliation.reconcile()

        # Verify list was called with status filter
        mock_repository.list.assert_called_once_with(status="RUNNING")
        # No updates should happen
        mock_repository.update.assert_not_called()
        # Result should reflect no operations processed
        assert result.total_processed == 0
        assert result.worker_ops_reconciled == 0
        assert result.backend_ops_failed == 0

    @pytest.mark.asyncio
    async def test_reconcile_worker_ops_marked_pending_reconciliation(
        self, mock_repository
    ):
        """Worker-based RUNNING operations should be marked PENDING_RECONCILIATION."""
        worker_op = _create_operation(
            "op_training_123",
            is_backend_local=False,
            worker_id="training-worker-abc",
        )
        mock_repository.list.return_value = [worker_op]

        reconciliation = StartupReconciliation(repository=mock_repository)
        result = await reconciliation.reconcile()

        # Verify update was called with reconciliation_status
        mock_repository.update.assert_called_once_with(
            "op_training_123",
            reconciliation_status="PENDING_RECONCILIATION",
        )
        assert result.total_processed == 1
        assert result.worker_ops_reconciled == 1
        assert result.backend_ops_failed == 0

    @pytest.mark.asyncio
    async def test_reconcile_backend_local_ops_marked_failed(self, mock_repository):
        """Backend-local RUNNING operations should be marked FAILED."""
        backend_op = _create_operation(
            "op_local_456",
            is_backend_local=True,
            worker_id=None,
        )
        mock_repository.list.return_value = [backend_op]

        reconciliation = StartupReconciliation(repository=mock_repository)
        result = await reconciliation.reconcile()

        # Verify update was called with FAILED status
        mock_repository.update.assert_called_once_with(
            "op_local_456",
            status="FAILED",
            error_message="Backend restarted - operation was running in backend process",
        )
        assert result.total_processed == 1
        assert result.worker_ops_reconciled == 0
        assert result.backend_ops_failed == 1

    @pytest.mark.asyncio
    async def test_reconcile_mixed_operations(self, mock_repository):
        """Reconcile should handle mix of worker-based and backend-local ops."""
        worker_op_1 = _create_operation(
            "op_worker_1",
            is_backend_local=False,
            worker_id="worker-a",
        )
        worker_op_2 = _create_operation(
            "op_worker_2",
            is_backend_local=False,
            worker_id="worker-b",
        )
        backend_op = _create_operation(
            "op_backend_1",
            is_backend_local=True,
            worker_id=None,
        )
        mock_repository.list.return_value = [worker_op_1, worker_op_2, backend_op]

        reconciliation = StartupReconciliation(repository=mock_repository)
        result = await reconciliation.reconcile()

        # Verify all operations were processed
        assert mock_repository.update.call_count == 3
        assert result.total_processed == 3
        assert result.worker_ops_reconciled == 2
        assert result.backend_ops_failed == 1

    @pytest.mark.asyncio
    async def test_reconcile_determines_backend_local_from_metadata(
        self, mock_repository
    ):
        """Should determine is_backend_local from operation metadata."""
        # Operation with is_backend_local=True in metadata
        op = _create_operation("op_test", is_backend_local=True, worker_id=None)
        mock_repository.list.return_value = [op]

        reconciliation = StartupReconciliation(repository=mock_repository)
        result = await reconciliation.reconcile()

        # Should be marked as FAILED (backend-local)
        mock_repository.update.assert_called_once()
        call_kwargs = mock_repository.update.call_args.kwargs
        assert call_kwargs.get("status") == "FAILED"
        assert result.backend_ops_failed == 1

    @pytest.mark.asyncio
    async def test_reconcile_without_worker_id_treated_as_backend_local(
        self, mock_repository
    ):
        """Operations without worker_id should be treated as backend-local."""
        # Operation with no worker_id and is_backend_local=False should still
        # be treated based on is_backend_local flag
        op = _create_operation("op_orphan", is_backend_local=False, worker_id=None)
        mock_repository.list.return_value = [op]

        reconciliation = StartupReconciliation(repository=mock_repository)
        result = await reconciliation.reconcile()

        # Should be marked as PENDING_RECONCILIATION (worker-based, even without worker_id)
        # because is_backend_local is False
        mock_repository.update.assert_called_once_with(
            "op_orphan",
            reconciliation_status="PENDING_RECONCILIATION",
        )
        assert result.worker_ops_reconciled == 1

    @pytest.mark.asyncio
    async def test_reconcile_logs_summary(self, mock_repository, caplog):
        """Reconcile should log a summary of processed operations."""
        import logging

        worker_op = _create_operation("op_worker", is_backend_local=False)
        backend_op = _create_operation("op_backend", is_backend_local=True)
        mock_repository.list.return_value = [worker_op, backend_op]

        with caplog.at_level(logging.INFO):
            reconciliation = StartupReconciliation(repository=mock_repository)
            await reconciliation.reconcile()

        # Check that a summary was logged
        assert any(
            "reconciliation" in record.message.lower() for record in caplog.records
        )
        assert any("2" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_reconcile_handles_empty_metadata(self, mock_repository):
        """Reconcile should handle operations with empty/missing metadata gracefully."""
        op = OperationInfo(
            operation_id="op_empty_meta",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc),
            progress=OperationProgress(percentage=0.0),
            metadata=OperationMetadata(),  # Empty metadata
        )
        mock_repository.list.return_value = [op]

        reconciliation = StartupReconciliation(repository=mock_repository)
        result = await reconciliation.reconcile()

        # Should default to worker-based (is_backend_local=False by default)
        mock_repository.update.assert_called_once_with(
            "op_empty_meta",
            reconciliation_status="PENDING_RECONCILIATION",
        )
        assert result.worker_ops_reconciled == 1
