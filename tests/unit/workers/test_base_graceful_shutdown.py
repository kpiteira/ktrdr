"""Tests for WorkerAPIBase graceful shutdown operation execution (M6 Task 6.2)."""

import asyncio

import pytest

from ktrdr.api.models.operations import OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.workers.base import GracefulShutdownError, WorkerAPIBase


class MockWorker(WorkerAPIBase):
    """Mock worker for testing graceful shutdown."""

    def __init__(self):
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url="http://backend:8000",
        )
        # Track calls to hook methods for testing
        self.save_checkpoint_calls: list[tuple[str, str]] = []
        self.update_status_calls: list[tuple[str, str, str | None]] = []

    async def _save_checkpoint(self, operation_id: str, checkpoint_type: str) -> None:
        """Override to track calls."""
        self.save_checkpoint_calls.append((operation_id, checkpoint_type))

    async def _update_operation_status(
        self, operation_id: str, status: str, error_message: str | None = None
    ) -> None:
        """Override to track calls."""
        self.update_status_calls.append((operation_id, status, error_message))


class TestGracefulShutdownError:
    """Tests for GracefulShutdownError exception (Task 6.2)."""

    def test_graceful_shutdown_error_exists(self):
        """Test GracefulShutdownError exception class exists."""
        assert GracefulShutdownError is not None
        assert issubclass(GracefulShutdownError, Exception)

    def test_graceful_shutdown_error_message(self):
        """Test GracefulShutdownError can be raised with message."""
        error = GracefulShutdownError("Worker shutdown requested")
        assert str(error) == "Worker shutdown requested"


class TestCurrentOperationTracking:
    """Tests for _current_operation_id tracking (Task 6.2)."""

    def test_current_operation_id_initialized_to_none(self):
        """Test _current_operation_id is initialized to None."""
        worker = MockWorker()
        assert hasattr(worker, "_current_operation_id")
        assert worker._current_operation_id is None


class TestRunWithGracefulShutdown:
    """Tests for run_with_graceful_shutdown method (Task 6.2)."""

    def test_run_with_graceful_shutdown_exists(self):
        """Test run_with_graceful_shutdown method exists."""
        worker = MockWorker()
        assert hasattr(worker, "run_with_graceful_shutdown")
        assert asyncio.iscoroutinefunction(worker.run_with_graceful_shutdown)

    @pytest.mark.asyncio
    async def test_operation_completes_normally(self):
        """Test operation completes normally when no shutdown signal."""
        worker = MockWorker()

        async def operation():
            return "completed"

        result = await worker.run_with_graceful_shutdown("op_123", operation())
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_current_operation_id_set_during_execution(self):
        """Test _current_operation_id is set while operation runs."""
        worker = MockWorker()
        captured_id = None

        async def operation():
            nonlocal captured_id
            captured_id = worker._current_operation_id
            return "done"

        await worker.run_with_graceful_shutdown("op_456", operation())
        assert captured_id == "op_456"

    @pytest.mark.asyncio
    async def test_current_operation_id_cleared_after_completion(self):
        """Test _current_operation_id is cleared after operation completes."""
        worker = MockWorker()

        async def operation():
            return "done"

        await worker.run_with_graceful_shutdown("op_789", operation())
        assert worker._current_operation_id is None

    @pytest.mark.asyncio
    async def test_current_operation_id_cleared_on_exception(self):
        """Test _current_operation_id is cleared even when operation raises."""
        worker = MockWorker()

        async def failing_operation():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await worker.run_with_graceful_shutdown("op_error", failing_operation())

        assert worker._current_operation_id is None


class TestShutdownDetection:
    """Tests for shutdown detection during operation (Task 6.2)."""

    @pytest.mark.asyncio
    async def test_stale_shutdown_event_cleared_at_operation_start(self):
        """Test that a stale shutdown event from a previous operation is cleared.

        This prevents the bug where a SIGTERM during one operation would cause
        all subsequent operations to immediately cancel.
        """
        worker = MockWorker()

        # Simulate stale shutdown event from previous operation
        worker._shutdown_event.set()

        # New operation should complete normally (event cleared at start)
        async def quick_operation():
            return "completed"

        result = await worker.run_with_graceful_shutdown("op_new", quick_operation())
        assert result == "completed"

        # Event should have been cleared
        assert not worker._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_detected_during_operation(self):
        """Test shutdown is detected when signal received during operation."""
        worker = MockWorker()
        operation_started = asyncio.Event()
        operation_cancelled = False

        async def long_operation():
            nonlocal operation_cancelled
            operation_started.set()
            try:
                await asyncio.sleep(10)  # Long operation
                return "should not complete"
            except asyncio.CancelledError:
                operation_cancelled = True
                raise

        async def trigger_shutdown():
            await operation_started.wait()
            await asyncio.sleep(0.01)  # Small delay
            worker._shutdown_event.set()

        # Run operation and shutdown trigger concurrently
        shutdown_task = asyncio.create_task(trigger_shutdown())

        with pytest.raises(GracefulShutdownError):
            await worker.run_with_graceful_shutdown("op_shutdown", long_operation())

        await shutdown_task
        assert operation_cancelled

    @pytest.mark.asyncio
    async def test_checkpoint_saved_on_shutdown(self):
        """Test checkpoint is saved with type='shutdown' when shutdown detected."""
        worker = MockWorker()
        operation_started = asyncio.Event()

        async def long_operation():
            operation_started.set()
            await asyncio.sleep(10)

        async def trigger_shutdown():
            await operation_started.wait()
            await asyncio.sleep(0.01)  # Small delay to ensure operation is running
            worker._shutdown_event.set()

        shutdown_task = asyncio.create_task(trigger_shutdown())

        with pytest.raises(GracefulShutdownError):
            await worker.run_with_graceful_shutdown("op_ckpt", long_operation())

        await shutdown_task

        # Verify checkpoint was saved with correct type
        assert len(worker.save_checkpoint_calls) == 1
        assert worker.save_checkpoint_calls[0] == ("op_ckpt", "shutdown")

    @pytest.mark.asyncio
    async def test_status_updated_to_cancelled_on_shutdown(self):
        """Test operation status is updated to CANCELLED on shutdown."""
        worker = MockWorker()
        operation_started = asyncio.Event()

        async def long_operation():
            operation_started.set()
            await asyncio.sleep(10)

        async def trigger_shutdown():
            await operation_started.wait()
            await asyncio.sleep(0.01)
            worker._shutdown_event.set()

        shutdown_task = asyncio.create_task(trigger_shutdown())

        with pytest.raises(GracefulShutdownError):
            await worker.run_with_graceful_shutdown("op_cancel", long_operation())

        await shutdown_task

        # Verify status was updated
        assert len(worker.update_status_calls) == 1
        op_id, status, msg = worker.update_status_calls[0]
        assert op_id == "op_cancel"
        assert status == "CANCELLED"
        assert msg is not None and "shutdown" in msg.lower()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_error_raised(self):
        """Test GracefulShutdownError is raised when shutdown detected."""
        worker = MockWorker()
        operation_started = asyncio.Event()

        async def long_operation():
            operation_started.set()
            await asyncio.sleep(10)

        async def trigger_shutdown():
            await operation_started.wait()
            await asyncio.sleep(0.01)
            worker._shutdown_event.set()

        shutdown_task = asyncio.create_task(trigger_shutdown())

        with pytest.raises(GracefulShutdownError, match="shutdown"):
            await worker.run_with_graceful_shutdown("op_err", long_operation())

        await shutdown_task


class TestFailureCheckpoint:
    """Tests for failure checkpoint on non-shutdown exceptions (Task 6.2)."""

    @pytest.mark.asyncio
    async def test_failure_checkpoint_saved_on_exception(self):
        """Test checkpoint is saved with type='failure' on non-shutdown exception."""
        worker = MockWorker()

        async def failing_operation():
            raise ValueError("Operation failed")

        with pytest.raises(ValueError):
            await worker.run_with_graceful_shutdown("op_fail", failing_operation())

        # Verify failure checkpoint was saved
        assert len(worker.save_checkpoint_calls) == 1
        assert worker.save_checkpoint_calls[0] == ("op_fail", "failure")

    @pytest.mark.asyncio
    async def test_no_failure_checkpoint_on_graceful_shutdown(self):
        """Test failure checkpoint is NOT saved when GracefulShutdownError occurs."""
        worker = MockWorker()
        operation_started = asyncio.Event()

        async def long_operation():
            operation_started.set()
            await asyncio.sleep(10)

        async def trigger_shutdown():
            await operation_started.wait()
            await asyncio.sleep(0.01)
            worker._shutdown_event.set()

        shutdown_task = asyncio.create_task(trigger_shutdown())

        with pytest.raises(GracefulShutdownError):
            await worker.run_with_graceful_shutdown("op_no_fail", long_operation())

        await shutdown_task

        # Should only have shutdown checkpoint, not failure
        assert len(worker.save_checkpoint_calls) == 1
        assert worker.save_checkpoint_calls[0][1] == "shutdown"


class TestHookMethods:
    """Tests for _save_checkpoint and _update_operation_status hook methods."""

    def test_save_checkpoint_method_exists(self):
        """Test _save_checkpoint method exists on base class."""
        # Use base class, not mock
        worker = WorkerAPIBase(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url="http://backend:8000",
        )
        assert hasattr(worker, "_save_checkpoint")
        assert asyncio.iscoroutinefunction(worker._save_checkpoint)

    def test_update_operation_status_method_exists(self):
        """Test _update_operation_status method exists on base class."""
        worker = WorkerAPIBase(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url="http://backend:8000",
        )
        assert hasattr(worker, "_update_operation_status")
        assert asyncio.iscoroutinefunction(worker._update_operation_status)

    @pytest.mark.asyncio
    async def test_save_checkpoint_base_implementation_is_noop(self):
        """Test base _save_checkpoint does nothing (hook for subclasses)."""
        worker = WorkerAPIBase(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url="http://backend:8000",
        )
        # Should not raise - just a no-op
        await worker._save_checkpoint("op_test", "shutdown")

    @pytest.mark.asyncio
    async def test_update_operation_status_base_is_stub(self):
        """Test base _update_operation_status is stub (implemented in Task 6.3)."""
        worker = WorkerAPIBase(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url="http://backend:8000",
        )
        # Should not raise - stub for Task 6.3
        await worker._update_operation_status("op_test", "CANCELLED")
