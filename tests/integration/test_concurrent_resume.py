"""Integration tests for M8 Task 8.1: Concurrent Resume Protection.

This test suite verifies that concurrent resume requests are handled correctly
via optimistic locking. When multiple resume requests are fired simultaneously
for the same operation, exactly one should succeed and others should receive
conflict errors.

The protection mechanism works at the database level via atomic UPDATE:
  UPDATE operations SET status = 'resuming' ...
  WHERE operation_id = ? AND status IN ('cancelled', 'failed')

Only the first request to execute this UPDATE will find a matching row.
Subsequent requests find status = 'resuming' (no longer resumable) and fail.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from ktrdr.api.services.operations_service import OperationsService
from ktrdr.checkpoint.schemas import TrainingCheckpointState
from tests.integration.fixtures.checkpoint_mocks import (
    IntegrationCheckpointService,
    MockOperationsRepository,
)

# ============================================================================
# Test Infrastructure: Extended mock with concurrency support
# ============================================================================


class ConcurrencyTestRepository(MockOperationsRepository):
    """Operations repository with atomic try_resume for concurrency testing.

    Uses asyncio.Lock to simulate database-level atomic UPDATE behavior.
    This mimics the real OperationsRepository.try_resume which uses SQL
    atomic UPDATE with WHERE clause.
    """

    def __init__(self):
        super().__init__()
        self._resume_lock = asyncio.Lock()
        self.resume_attempts: list[tuple[str, bool, str]] = (
            []
        )  # (op_id, success, timestamp)

    async def create(
        self,
        operation_id: str,
        operation_type: str,
        status: str = "pending",
        metadata: dict | None = None,
    ) -> dict:
        """Create a new operation with metadata support."""
        self.operations[operation_id] = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "status": status,
            "created_at": datetime.now(timezone.utc),
            "started_at": None,
            "completed_at": None,
            "progress_percent": 0,
            "error_message": None,
            "metadata": metadata or {},
        }
        return self.operations[operation_id]

    async def try_resume(self, operation_id: str) -> bool:
        """Atomically update status to RESUMING if resumable.

        Simulates database-level atomic UPDATE with WHERE clause.
        Uses lock to ensure only one concurrent call succeeds.
        """
        async with self._resume_lock:
            op = self.operations.get(operation_id)
            timestamp = datetime.now(timezone.utc).isoformat()

            if op and op["status"] in ("cancelled", "failed"):
                op["status"] = "resuming"
                op["started_at"] = datetime.now(timezone.utc)
                op["completed_at"] = None
                op["error_message"] = None
                self.resume_attempts.append((operation_id, True, timestamp))
                return True

            # Operation not found or not in resumable state
            self.resume_attempts.append((operation_id, False, timestamp))
            return False

    async def get(self, operation_id: str) -> dict | None:
        """Get operation record."""
        return self.operations.get(operation_id)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def checkpoint_service():
    """Create IntegrationCheckpointService."""
    return IntegrationCheckpointService(artifacts_dir=None)


@pytest.fixture
def operations_repo():
    """Create ConcurrencyTestRepository."""
    return ConcurrencyTestRepository()


@pytest.fixture
def operations_service(operations_repo):
    """Create OperationsService with mock repository."""
    service = OperationsService()
    service._repository = operations_repo
    return service


def create_training_checkpoint_state(epoch: int = 29) -> dict:
    """Create training checkpoint state dict."""
    state = TrainingCheckpointState(
        epoch=epoch,
        train_loss=0.28,
        val_loss=0.31,
        best_val_loss=0.29,
        learning_rate=0.001,
    )
    # Add operation_type for resume endpoint dispatch
    result = state.to_dict()
    result["operation_type"] = "training"
    return result


async def create_cancelled_operation_with_checkpoint(
    operations_repo: ConcurrencyTestRepository,
    checkpoint_service: IntegrationCheckpointService,
    operation_id: str = "op_training_concurrent_test",
) -> str:
    """Create a cancelled operation with checkpoint for testing.

    Args:
        operations_repo: The operations repository
        checkpoint_service: The checkpoint service
        operation_id: ID for the operation

    Returns:
        The operation ID
    """
    # Create operation in cancelled state
    await operations_repo.create(
        operation_id=operation_id,
        operation_type="training",
        status="cancelled",
        metadata={"epoch": 29, "total_epochs": 100},
    )

    # Save checkpoint
    state = create_training_checkpoint_state(epoch=29)
    await checkpoint_service.save_checkpoint(
        operation_id=operation_id,
        checkpoint_type="cancellation",
        state=state,
    )

    return operation_id


# ============================================================================
# Test: Concurrent Resume Protection
# ============================================================================


class TestConcurrentResumeProtection:
    """Tests for concurrent resume request handling."""

    @pytest.mark.asyncio
    async def test_concurrent_resume_exactly_one_succeeds(
        self,
        operations_repo: ConcurrencyTestRepository,
        checkpoint_service: IntegrationCheckpointService,
        operations_service: OperationsService,
    ):
        """Only one of multiple concurrent resume requests should succeed.

        This test verifies the optimistic locking behavior where:
        - Multiple concurrent resume requests are fired
        - Exactly one request succeeds (first to acquire lock)
        - All other requests fail with False return
        - Final state is consistent (status = resuming)
        """
        # Create cancelled operation with checkpoint
        op_id = await create_cancelled_operation_with_checkpoint(
            operations_repo, checkpoint_service
        )

        # Fire 3 concurrent resume requests
        results = await asyncio.gather(
            operations_service.try_resume(op_id),
            operations_service.try_resume(op_id),
            operations_service.try_resume(op_id),
            return_exceptions=True,
        )

        # Count successes and failures
        successes = [r for r in results if r is True]
        failures = [r for r in results if r is False]
        exceptions = [r for r in results if isinstance(r, Exception)]

        # Exactly one should succeed
        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
        assert len(failures) == 2, f"Expected 2 failures, got {len(failures)}"
        assert len(exceptions) == 0, f"Unexpected exceptions: {exceptions}"

        # Verify final state is consistent
        op = await operations_repo.get(op_id)
        assert op is not None
        assert op["status"] == "resuming"

    @pytest.mark.asyncio
    async def test_concurrent_resume_five_requests(
        self,
        operations_repo: ConcurrencyTestRepository,
        checkpoint_service: IntegrationCheckpointService,
        operations_service: OperationsService,
    ):
        """Test with higher concurrency - 5 simultaneous requests."""
        op_id = await create_cancelled_operation_with_checkpoint(
            operations_repo, checkpoint_service, "op_concurrent_five"
        )

        # Fire 5 concurrent resume requests
        results = await asyncio.gather(
            *[operations_service.try_resume(op_id) for _ in range(5)],
            return_exceptions=True,
        )

        # Count results
        successes = [r for r in results if r is True]
        failures = [r for r in results if r is False]

        # Exactly one should succeed
        assert len(successes) == 1
        assert len(failures) == 4

    @pytest.mark.asyncio
    async def test_concurrent_resume_tracks_all_attempts(
        self,
        operations_repo: ConcurrencyTestRepository,
        checkpoint_service: IntegrationCheckpointService,
        operations_service: OperationsService,
    ):
        """Verify all resume attempts are recorded for debugging."""
        op_id = await create_cancelled_operation_with_checkpoint(
            operations_repo, checkpoint_service, "op_track_attempts"
        )

        # Fire concurrent requests
        await asyncio.gather(
            *[operations_service.try_resume(op_id) for _ in range(3)],
            return_exceptions=True,
        )

        # All attempts should be tracked
        attempts = operations_repo.resume_attempts
        assert len(attempts) == 3

        # Exactly one success
        successful = [a for a in attempts if a[1] is True]
        assert len(successful) == 1

    @pytest.mark.asyncio
    async def test_concurrent_resume_no_race_condition_on_state(
        self,
        operations_repo: ConcurrencyTestRepository,
        checkpoint_service: IntegrationCheckpointService,
        operations_service: OperationsService,
    ):
        """Verify no race condition leads to inconsistent state.

        The operation should always be in 'resuming' state after concurrent
        attempts, never in an intermediate or corrupted state.
        """
        op_id = await create_cancelled_operation_with_checkpoint(
            operations_repo, checkpoint_service, "op_race_check"
        )

        # Fire concurrent requests
        await asyncio.gather(
            *[operations_service.try_resume(op_id) for _ in range(10)],
            return_exceptions=True,
        )

        # Verify consistent final state
        op = await operations_repo.get(op_id)
        assert op is not None

        # Status must be exactly 'resuming' - not cancelled, not some weird state
        assert op["status"] == "resuming"

        # started_at should be set
        assert op["started_at"] is not None

        # completed_at and error_message should be cleared
        assert op["completed_at"] is None
        assert op["error_message"] is None


class TestConcurrentResumeFromFailedState:
    """Tests for concurrent resume of failed operations."""

    @pytest.mark.asyncio
    async def test_concurrent_resume_failed_operation(
        self,
        operations_repo: ConcurrencyTestRepository,
        checkpoint_service: IntegrationCheckpointService,
        operations_service: OperationsService,
    ):
        """Concurrent resume of failed operation - exactly one succeeds."""
        op_id = "op_failed_concurrent"

        # Create FAILED operation (not cancelled)
        await operations_repo.create(
            operation_id=op_id,
            operation_type="training",
            status="failed",
            metadata={"epoch": 45},
        )

        # Save checkpoint
        await checkpoint_service.save_checkpoint(
            operation_id=op_id,
            checkpoint_type="failure",
            state=create_training_checkpoint_state(epoch=45),
        )

        # Fire concurrent requests
        results = await asyncio.gather(
            *[operations_service.try_resume(op_id) for _ in range(3)],
            return_exceptions=True,
        )

        successes = [r for r in results if r is True]
        assert len(successes) == 1


class TestConcurrentResumeEdgeCases:
    """Edge cases for concurrent resume."""

    @pytest.mark.asyncio
    async def test_concurrent_resume_different_operations(
        self,
        operations_repo: ConcurrencyTestRepository,
        checkpoint_service: IntegrationCheckpointService,
        operations_service: OperationsService,
    ):
        """Concurrent resume of different operations - all should succeed."""
        op_ids = []
        for i in range(3):
            op_id = await create_cancelled_operation_with_checkpoint(
                operations_repo, checkpoint_service, f"op_different_{i}"
            )
            op_ids.append(op_id)

        # Fire concurrent requests for different operations
        results = await asyncio.gather(
            *[operations_service.try_resume(op_id) for op_id in op_ids],
            return_exceptions=True,
        )

        # All should succeed (different operations don't conflict)
        successes = [r for r in results if r is True]
        assert len(successes) == 3

    @pytest.mark.asyncio
    async def test_resume_already_resuming_operation_fails(
        self,
        operations_repo: ConcurrencyTestRepository,
        checkpoint_service: IntegrationCheckpointService,
        operations_service: OperationsService,
    ):
        """Resume request for already-resuming operation should fail."""
        op_id = await create_cancelled_operation_with_checkpoint(
            operations_repo, checkpoint_service, "op_already_resuming"
        )

        # First resume
        result1 = await operations_service.try_resume(op_id)
        assert result1 is True

        # Status is now 'resuming'
        op = await operations_repo.get(op_id)
        assert op["status"] == "resuming"

        # Second resume should fail
        result2 = await operations_service.try_resume(op_id)
        assert result2 is False

    @pytest.mark.asyncio
    async def test_resume_running_operation_fails(
        self,
        operations_repo: ConcurrencyTestRepository,
        checkpoint_service: IntegrationCheckpointService,
        operations_service: OperationsService,
    ):
        """Resume request for running operation should fail."""
        op_id = "op_running"

        # Create running operation
        await operations_repo.create(
            operation_id=op_id,
            operation_type="training",
            status="running",
        )

        # Resume should fail
        result = await operations_service.try_resume(op_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_resume_completed_operation_fails(
        self,
        operations_repo: ConcurrencyTestRepository,
        checkpoint_service: IntegrationCheckpointService,
        operations_service: OperationsService,
    ):
        """Resume request for completed operation should fail."""
        op_id = "op_completed"

        # Create completed operation
        await operations_repo.create(
            operation_id=op_id,
            operation_type="training",
            status="completed",
        )

        # Resume should fail
        result = await operations_service.try_resume(op_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_resume_nonexistent_operation_fails(
        self,
        operations_repo: ConcurrencyTestRepository,
        operations_service: OperationsService,
    ):
        """Resume request for nonexistent operation should fail gracefully."""
        result = await operations_service.try_resume("op_does_not_exist")
        assert result is False
