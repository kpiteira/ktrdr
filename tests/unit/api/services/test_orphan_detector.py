"""Unit tests for OrphanOperationDetector service.

Tests the orphan detection logic that finds RUNNING/PENDING_RECONCILIATION
operations with no worker claiming them and marks them FAILED after timeout.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.api.models.workers import WorkerEndpoint, WorkerStatus, WorkerType
from ktrdr.api.services.orphan_detector import OrphanOperationDetector


def _create_operation(
    operation_id: str,
    status: OperationStatus = OperationStatus.RUNNING,
    is_backend_local: bool = False,
    worker_id: str | None = "worker-123",
    reconciliation_status: str | None = None,
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
                "worker_id": worker_id,
                "reconciliation_status": reconciliation_status,
            },
        ),
        is_backend_local=is_backend_local,
    )


def _create_worker(
    worker_id: str,
    worker_type: WorkerType = WorkerType.TRAINING,
    status: WorkerStatus = WorkerStatus.BUSY,
    current_operation_id: str | None = None,
) -> WorkerEndpoint:
    """Create a test worker endpoint."""
    return WorkerEndpoint(
        worker_id=worker_id,
        worker_type=worker_type,
        endpoint_url=f"http://localhost:500{worker_id[-1]}",
        status=status,
        current_operation_id=current_operation_id,
    )


@pytest.fixture
def mock_operations_service():
    """Create a mock OperationsService."""
    service = AsyncMock()
    service.list_operations = AsyncMock(return_value=([], 0, 0))
    service.fail_operation = AsyncMock()
    return service


@pytest.fixture
def mock_worker_registry():
    """Create a mock WorkerRegistry."""
    registry = MagicMock()
    registry.list_workers = MagicMock(return_value=[])
    return registry


class TestOrphanOperationDetector:
    """Test OrphanOperationDetector service (Task 2.1)."""

    def test_init_with_default_config(
        self, mock_operations_service, mock_worker_registry
    ):
        """OrphanOperationDetector should initialize with default timeout and interval."""
        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
        )

        assert detector._orphan_timeout == 60
        assert detector._check_interval == 15
        assert detector._task is None
        assert detector._potential_orphans == {}

    def test_init_with_custom_config(
        self, mock_operations_service, mock_worker_registry
    ):
        """OrphanOperationDetector should accept custom timeout and interval."""
        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
            orphan_timeout_seconds=120,
            check_interval_seconds=30,
        )

        assert detector._orphan_timeout == 120
        assert detector._check_interval == 30

    @pytest.mark.asyncio
    async def test_check_for_orphans_no_running_operations(
        self, mock_operations_service, mock_worker_registry
    ):
        """No orphans should be detected when no RUNNING operations exist."""
        mock_operations_service.list_operations.return_value = ([], 0, 0)

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
        )
        await detector._check_for_orphans()

        # Should query operations but not fail any
        mock_operations_service.list_operations.assert_called_once()
        mock_operations_service.fail_operation.assert_not_called()
        assert len(detector._potential_orphans) == 0

    @pytest.mark.asyncio
    async def test_check_for_orphans_operation_claimed_by_worker(
        self, mock_operations_service, mock_worker_registry
    ):
        """Operations claimed by workers should not be flagged as orphans."""
        running_op = _create_operation("op_training_123")
        worker = _create_worker(
            "training-worker-1", current_operation_id="op_training_123"
        )

        mock_operations_service.list_operations.return_value = ([running_op], 1, 1)
        mock_worker_registry.list_workers.return_value = [worker]

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
        )
        await detector._check_for_orphans()

        # Operation should not be tracked as potential orphan
        mock_operations_service.fail_operation.assert_not_called()
        assert "op_training_123" not in detector._potential_orphans

    @pytest.mark.asyncio
    async def test_check_for_orphans_first_detection_tracks_but_not_fails(
        self, mock_operations_service, mock_worker_registry
    ):
        """First detection of orphan should track it but not fail it yet."""
        running_op = _create_operation("op_training_123")
        mock_operations_service.list_operations.return_value = ([running_op], 1, 1)
        mock_worker_registry.list_workers.return_value = []  # No workers

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
        )
        await detector._check_for_orphans()

        # Should track as potential orphan but not fail yet
        mock_operations_service.fail_operation.assert_not_called()
        assert "op_training_123" in detector._potential_orphans

    @pytest.mark.asyncio
    async def test_check_for_orphans_timeout_exceeded_marks_failed(
        self, mock_operations_service, mock_worker_registry
    ):
        """Operation should be marked FAILED when timeout exceeded."""
        running_op = _create_operation("op_training_123")
        mock_operations_service.list_operations.return_value = ([running_op], 1, 1)
        mock_worker_registry.list_workers.return_value = []  # No workers

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
            orphan_timeout_seconds=60,
        )

        # Pre-populate potential_orphans with old timestamp (past timeout)
        detector._potential_orphans["op_training_123"] = datetime.now(
            timezone.utc
        ) - timedelta(seconds=70)

        await detector._check_for_orphans()

        # Should mark operation as failed
        mock_operations_service.fail_operation.assert_called_once()
        call_args = mock_operations_service.fail_operation.call_args
        assert call_args[0][0] == "op_training_123"
        assert "no worker claimed it" in call_args[1]["error_message"].lower()

        # Should be removed from tracking
        assert "op_training_123" not in detector._potential_orphans

    @pytest.mark.asyncio
    async def test_check_for_orphans_timeout_not_exceeded_keeps_tracking(
        self, mock_operations_service, mock_worker_registry
    ):
        """Operation should stay tracked when timeout not exceeded."""
        running_op = _create_operation("op_training_123")
        mock_operations_service.list_operations.return_value = ([running_op], 1, 1)
        mock_worker_registry.list_workers.return_value = []  # No workers

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
            orphan_timeout_seconds=60,
        )

        # Pre-populate potential_orphans with recent timestamp (within timeout)
        first_seen = datetime.now(timezone.utc) - timedelta(seconds=30)
        detector._potential_orphans["op_training_123"] = first_seen

        await detector._check_for_orphans()

        # Should NOT fail yet
        mock_operations_service.fail_operation.assert_not_called()
        # Should still be tracked with original timestamp
        assert detector._potential_orphans["op_training_123"] == first_seen

    @pytest.mark.asyncio
    async def test_check_for_orphans_worker_claims_removes_from_tracking(
        self, mock_operations_service, mock_worker_registry
    ):
        """When worker claims an operation, it should be removed from tracking."""
        running_op = _create_operation("op_training_123")
        worker = _create_worker(
            "training-worker-1", current_operation_id="op_training_123"
        )

        mock_operations_service.list_operations.return_value = ([running_op], 1, 1)
        mock_worker_registry.list_workers.return_value = [worker]

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
        )

        # Pre-populate as if it was previously tracked
        detector._potential_orphans["op_training_123"] = datetime.now(
            timezone.utc
        ) - timedelta(seconds=30)

        await detector._check_for_orphans()

        # Should be removed from tracking since worker claimed it
        mock_operations_service.fail_operation.assert_not_called()
        assert "op_training_123" not in detector._potential_orphans

    @pytest.mark.asyncio
    async def test_check_for_orphans_ignores_backend_local_operations(
        self, mock_operations_service, mock_worker_registry
    ):
        """Backend-local operations should be ignored (handled by StartupReconciliation)."""
        backend_local_op = _create_operation(
            "op_agent_123", is_backend_local=True, worker_id=None
        )
        mock_operations_service.list_operations.return_value = (
            [backend_local_op],
            1,
            1,
        )
        mock_worker_registry.list_workers.return_value = []

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
        )
        await detector._check_for_orphans()

        # Backend-local operations should not be tracked as orphans
        mock_operations_service.fail_operation.assert_not_called()
        assert "op_agent_123" not in detector._potential_orphans

    @pytest.mark.asyncio
    async def test_check_for_orphans_handles_pending_reconciliation_status(
        self, mock_operations_service, mock_worker_registry
    ):
        """Operations with PENDING_RECONCILIATION should also be checked."""
        # Create operation that's RUNNING but marked for reconciliation
        reconciling_op = _create_operation(
            "op_training_123",
            reconciliation_status="PENDING_RECONCILIATION",
        )
        mock_operations_service.list_operations.return_value = ([reconciling_op], 1, 1)
        mock_worker_registry.list_workers.return_value = []  # No workers

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
            orphan_timeout_seconds=60,
        )

        # Pre-populate with old timestamp
        detector._potential_orphans["op_training_123"] = datetime.now(
            timezone.utc
        ) - timedelta(seconds=70)

        await detector._check_for_orphans()

        # Should mark as failed
        mock_operations_service.fail_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_for_orphans_multiple_operations(
        self, mock_operations_service, mock_worker_registry
    ):
        """Should handle multiple operations with different states correctly."""
        # Operation 1: Claimed by worker (not orphan)
        op1 = _create_operation("op_claimed")
        # Operation 2: Not claimed, recently seen (track but don't fail)
        op2 = _create_operation("op_new_orphan")
        # Operation 3: Not claimed, timeout exceeded (fail it)
        op3 = _create_operation("op_old_orphan")

        worker = _create_worker("worker-1", current_operation_id="op_claimed")

        mock_operations_service.list_operations.return_value = ([op1, op2, op3], 3, 3)
        mock_worker_registry.list_workers.return_value = [worker]

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
            orphan_timeout_seconds=60,
        )

        # Pre-populate: op_old_orphan seen 70 seconds ago
        detector._potential_orphans["op_old_orphan"] = datetime.now(
            timezone.utc
        ) - timedelta(seconds=70)

        await detector._check_for_orphans()

        # op_claimed: not tracked
        assert "op_claimed" not in detector._potential_orphans
        # op_new_orphan: now tracked
        assert "op_new_orphan" in detector._potential_orphans
        # op_old_orphan: failed and removed
        assert "op_old_orphan" not in detector._potential_orphans
        mock_operations_service.fail_operation.assert_called_once_with(
            "op_old_orphan",
            error_message="Operation was RUNNING but no worker claimed it",
        )

    @pytest.mark.asyncio
    async def test_check_for_orphans_cleans_up_stale_entries(
        self, mock_operations_service, mock_worker_registry
    ):
        """Operations no longer RUNNING should be removed from potential orphans."""
        # No running operations
        mock_operations_service.list_operations.return_value = ([], 0, 0)
        mock_worker_registry.list_workers.return_value = []

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
        )

        # Simulate that we were tracking these as potential orphans
        # (e.g., they transitioned to COMPLETED/FAILED outside the detector)
        detector._potential_orphans["op_completed"] = datetime.now(
            timezone.utc
        ) - timedelta(seconds=30)
        detector._potential_orphans["op_failed"] = datetime.now(
            timezone.utc
        ) - timedelta(seconds=45)

        await detector._check_for_orphans()

        # Both should be cleaned up since they're no longer in running_ops
        assert "op_completed" not in detector._potential_orphans
        assert "op_failed" not in detector._potential_orphans
        # fail_operation should NOT be called (they weren't orphaned, just completed)
        mock_operations_service.fail_operation.assert_not_called()


class TestOrphanOperationDetectorLifecycle:
    """Test OrphanOperationDetector start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_background_task(
        self, mock_operations_service, mock_worker_registry
    ):
        """Start should create a background task for detection loop."""
        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
        )

        assert detector._task is None

        await detector.start()

        assert detector._task is not None
        assert not detector._task.done()

        # Cleanup
        await detector.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_background_task(
        self, mock_operations_service, mock_worker_registry
    ):
        """Stop should cancel the background task cleanly."""
        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
        )

        await detector.start()
        task = detector._task

        await detector.stop()

        # Task should be cancelled
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_stop_when_not_started_is_safe(
        self, mock_operations_service, mock_worker_registry
    ):
        """Stop should be safe to call even if not started."""
        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
        )

        # Should not raise
        await detector.stop()

    @pytest.mark.asyncio
    async def test_detection_loop_runs_periodically(
        self, mock_operations_service, mock_worker_registry
    ):
        """Detection loop should call _check_for_orphans periodically."""
        mock_operations_service.list_operations.return_value = ([], 0, 0)

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
            check_interval_seconds=0.1,  # Fast for testing
        )

        await detector.start()

        # Wait for a few iterations
        import asyncio

        await asyncio.sleep(0.35)

        await detector.stop()

        # Should have been called multiple times
        assert mock_operations_service.list_operations.call_count >= 2


class TestOrphanOperationDetectorHealthStatus:
    """Test OrphanOperationDetector health/status reporting."""

    def test_get_status_when_not_running(
        self, mock_operations_service, mock_worker_registry
    ):
        """Status should show not running when task not started."""
        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
        )

        status = detector.get_status()

        assert status["running"] is False
        assert status["potential_orphans_count"] == 0
        assert status["last_check"] is None

    @pytest.mark.asyncio
    async def test_get_status_when_running(
        self, mock_operations_service, mock_worker_registry
    ):
        """Status should show running and track orphans."""
        # Create a running operation that will become an orphan (no worker claims it)
        running_op = _create_operation("op_123")
        mock_operations_service.list_operations.return_value = ([running_op], 1, 1)
        mock_worker_registry.list_workers.return_value = []  # No workers

        detector = OrphanOperationDetector(
            operations_service=mock_operations_service,
            worker_registry=mock_worker_registry,
            check_interval_seconds=0.1,
        )

        await detector.start()
        import asyncio

        await asyncio.sleep(0.15)

        status = detector.get_status()

        assert status["running"] is True
        # Operation should be tracked as potential orphan (no worker claims it)
        assert status["potential_orphans_count"] == 1
        assert status["last_check"] is not None

        await detector.stop()
