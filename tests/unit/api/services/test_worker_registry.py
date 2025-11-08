"""Unit tests for WorkerRegistry."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.api.models.workers import WorkerStatus, WorkerType
from ktrdr.api.services.worker_registry import WorkerRegistry


class TestWorkerRegistry:
    """Tests for WorkerRegistry class."""

    def test_init_creates_empty_registry(self):
        """Test that initialization creates an empty worker registry."""
        registry = WorkerRegistry()
        assert registry.list_workers() == []

    def test_register_worker_adds_new_worker(self):
        """Test registering a new worker."""
        registry = WorkerRegistry()

        worker = registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )

        assert worker.worker_id == "worker-1"
        assert worker.worker_type == WorkerType.BACKTESTING
        assert worker.endpoint_url == "http://localhost:5003"
        assert worker.status == WorkerStatus.AVAILABLE
        assert worker.capabilities == {}

    def test_register_worker_with_capabilities(self):
        """Test registering a worker with capabilities."""
        registry = WorkerRegistry()

        capabilities = {"cores": 4, "memory_gb": 8}
        worker = registry.register_worker(
            worker_id="worker-2",
            worker_type=WorkerType.CPU_TRAINING,
            endpoint_url="http://localhost:5004",
            capabilities=capabilities,
        )

        assert worker.worker_id == "worker-2"
        assert worker.capabilities == capabilities

    def test_register_worker_is_idempotent(self):
        """Test that re-registering a worker updates the existing one."""
        registry = WorkerRegistry()

        # Register worker first time
        worker1 = registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )

        # Re-register same worker with different URL
        worker2 = registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5555",  # Different URL
        )

        # Should update existing worker
        assert worker1.worker_id == worker2.worker_id
        assert worker2.endpoint_url == "http://localhost:5555"

        # Should only have one worker in registry
        workers = registry.list_workers()
        assert len(workers) == 1
        assert workers[0].endpoint_url == "http://localhost:5555"

    def test_get_worker_returns_existing_worker(self):
        """Test getting an existing worker by ID."""
        registry = WorkerRegistry()

        # Register a worker
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )

        # Get the worker
        worker = registry.get_worker("worker-1")

        assert worker is not None
        assert worker.worker_id == "worker-1"
        assert worker.worker_type == WorkerType.BACKTESTING

    def test_get_worker_returns_none_for_nonexistent_worker(self):
        """Test getting a nonexistent worker returns None."""
        registry = WorkerRegistry()

        worker = registry.get_worker("nonexistent-worker")

        assert worker is None

    def test_list_workers_returns_all_workers(self):
        """Test listing all workers."""
        registry = WorkerRegistry()

        # Register multiple workers
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )
        registry.register_worker(
            worker_id="worker-2",
            worker_type=WorkerType.CPU_TRAINING,
            endpoint_url="http://localhost:5004",
        )
        registry.register_worker(
            worker_id="worker-3",
            worker_type=WorkerType.GPU_HOST,
            endpoint_url="http://localhost:5002",
        )

        workers = registry.list_workers()

        assert len(workers) == 3
        worker_ids = {w.worker_id for w in workers}
        assert worker_ids == {"worker-1", "worker-2", "worker-3"}

    def test_list_workers_filter_by_type(self):
        """Test filtering workers by type."""
        registry = WorkerRegistry()

        # Register workers of different types
        registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )
        registry.register_worker(
            worker_id="backtest-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5004",
        )
        registry.register_worker(
            worker_id="training-1",
            worker_type=WorkerType.CPU_TRAINING,
            endpoint_url="http://localhost:5005",
        )

        # Filter by BACKTESTING type
        backtest_workers = registry.list_workers(worker_type=WorkerType.BACKTESTING)

        assert len(backtest_workers) == 2
        worker_ids = {w.worker_id for w in backtest_workers}
        assert worker_ids == {"backtest-1", "backtest-2"}

    def test_list_workers_filter_by_status(self):
        """Test filtering workers by status."""
        registry = WorkerRegistry()

        # Register workers
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )
        worker2 = registry.register_worker(
            worker_id="worker-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5004",
        )

        # Manually set one worker to BUSY for testing
        worker2.status = WorkerStatus.BUSY

        # Filter by AVAILABLE status
        available_workers = registry.list_workers(status=WorkerStatus.AVAILABLE)

        assert len(available_workers) == 1
        assert available_workers[0].worker_id == "worker-1"

    def test_list_workers_filter_by_type_and_status(self):
        """Test filtering workers by both type and status."""
        registry = WorkerRegistry()

        # Register various workers
        registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )
        worker2 = registry.register_worker(
            worker_id="backtest-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5004",
        )
        registry.register_worker(
            worker_id="training-1",
            worker_type=WorkerType.CPU_TRAINING,
            endpoint_url="http://localhost:5005",
        )

        # Set statuses
        worker2.status = WorkerStatus.BUSY

        # Filter by BACKTESTING and AVAILABLE
        filtered_workers = registry.list_workers(
            worker_type=WorkerType.BACKTESTING, status=WorkerStatus.AVAILABLE
        )

        assert len(filtered_workers) == 1
        assert filtered_workers[0].worker_id == "backtest-1"

    def test_register_worker_sets_last_healthy_at(self):
        """Test that registering a worker sets last_healthy_at timestamp."""
        registry = WorkerRegistry()

        before = datetime.utcnow()
        worker = registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )
        after = datetime.utcnow()

        assert worker.last_healthy_at is not None
        assert before <= worker.last_healthy_at <= after

    def test_get_available_workers_returns_only_available(self):
        """Test that get_available_workers returns only available workers."""
        registry = WorkerRegistry()

        # Register multiple workers
        registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )
        worker2 = registry.register_worker(
            worker_id="backtest-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5004",
        )
        registry.register_worker(
            worker_id="training-1",
            worker_type=WorkerType.CPU_TRAINING,
            endpoint_url="http://localhost:5005",
        )

        # Mark one backtest worker as busy
        worker2.status = WorkerStatus.BUSY

        # Get available backtesting workers
        available = registry.get_available_workers(WorkerType.BACKTESTING)

        assert len(available) == 1
        assert available[0].worker_id == "backtest-1"
        assert available[0].status == WorkerStatus.AVAILABLE

    def test_get_available_workers_sorted_by_last_selected(self):
        """Test that get_available_workers sorts by last_selected."""
        registry = WorkerRegistry()

        # Register multiple workers
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )
        registry.register_worker(
            worker_id="worker-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5004",
        )
        registry.register_worker(
            worker_id="worker-3",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5005",
        )

        # Manually set selection times (worker-2 selected most recently)
        registry.get_worker("worker-1").metadata["last_selected"] = 100.0
        registry.get_worker("worker-2").metadata["last_selected"] = 300.0  # Most recent
        registry.get_worker("worker-3").metadata["last_selected"] = 200.0

        # Get available workers - should be sorted by least recently used
        available = registry.get_available_workers(WorkerType.BACKTESTING)

        assert len(available) == 3
        assert available[0].worker_id == "worker-1"  # Least recently used
        assert available[1].worker_id == "worker-3"
        assert available[2].worker_id == "worker-2"  # Most recently used

    def test_select_worker_returns_least_recently_used(self):
        """Test that select_worker returns least recently used worker."""
        registry = WorkerRegistry()

        # Register workers
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )
        registry.register_worker(
            worker_id="worker-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5004",
        )

        # Set selection times
        registry.get_worker("worker-1").metadata["last_selected"] = 100.0
        registry.get_worker("worker-2").metadata["last_selected"] = 200.0

        # Select worker - should return least recently used
        worker = registry.select_worker(WorkerType.BACKTESTING)

        assert worker is not None
        assert worker.worker_id == "worker-1"

        # Verify last_selected was updated (should be > 200.0)
        assert worker.metadata["last_selected"] > 200.0

    def test_select_worker_round_robin_behavior(self):
        """Test that select_worker implements round-robin."""
        registry = WorkerRegistry()

        # Register 3 workers
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )
        registry.register_worker(
            worker_id="worker-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5004",
        )
        registry.register_worker(
            worker_id="worker-3",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5005",
        )

        # Select workers multiple times - should rotate
        selected_ids = []
        for _ in range(6):
            worker = registry.select_worker(WorkerType.BACKTESTING)
            assert worker is not None
            selected_ids.append(worker.worker_id)

        # Should cycle through all workers (not necessarily in order, but all should appear)
        # Each worker should be selected exactly twice in 6 selections
        from collections import Counter

        counts = Counter(selected_ids)
        assert len(counts) == 3  # All 3 workers selected
        assert all(count == 2 for count in counts.values())  # Each selected twice

    def test_select_worker_returns_none_when_no_workers(self):
        """Test that select_worker returns None when no workers available."""
        registry = WorkerRegistry()

        worker = registry.select_worker(WorkerType.BACKTESTING)

        assert worker is None

    def test_select_worker_returns_none_when_all_busy(self):
        """Test that select_worker returns None when all workers busy."""
        registry = WorkerRegistry()

        # Register workers
        worker1 = registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )
        worker2 = registry.register_worker(
            worker_id="worker-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5004",
        )

        # Mark all as busy
        worker1.status = WorkerStatus.BUSY
        worker2.status = WorkerStatus.BUSY

        # Should return None
        worker = registry.select_worker(WorkerType.BACKTESTING)

        assert worker is None

    def test_mark_busy_sets_status_and_operation(self):
        """Test that mark_busy sets worker status and operation_id."""
        registry = WorkerRegistry()

        # Register worker
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )

        # Mark as busy
        registry.mark_busy("worker-1", "op-123")

        # Verify status changed
        worker = registry.get_worker("worker-1")
        assert worker.status == WorkerStatus.BUSY
        assert worker.current_operation_id == "op-123"

    def test_mark_busy_nonexistent_worker_does_nothing(self):
        """Test that mark_busy on nonexistent worker doesn't crash."""
        registry = WorkerRegistry()

        # Should not raise exception
        registry.mark_busy("nonexistent", "op-123")

    def test_mark_available_clears_status_and_operation(self):
        """Test that mark_available clears worker status and operation_id."""
        registry = WorkerRegistry()

        # Register and mark busy
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
        )
        registry.mark_busy("worker-1", "op-123")

        # Mark as available
        registry.mark_available("worker-1")

        # Verify status cleared
        worker = registry.get_worker("worker-1")
        assert worker.status == WorkerStatus.AVAILABLE
        assert worker.current_operation_id is None

    def test_mark_available_nonexistent_worker_does_nothing(self):
        """Test that mark_available on nonexistent worker doesn't crash."""
        registry = WorkerRegistry()

        # Should not raise exception
        registry.mark_available("nonexistent")


class TestWorkerHealthChecks:
    """Tests for worker health check functionality."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Async httpx mocking complex - covered in integration tests")
    async def test_health_check_worker_success(self):
        """Test successful health check updates worker state."""
        registry = WorkerRegistry()

        # Register worker
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        # Mock successful health check response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "worker_status": "idle",
        }

        # Patch httpx.AsyncClient.get at the module level
        with patch(
            "ktrdr.api.services.worker_registry.httpx.AsyncClient.get",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = mock_response
            result = await registry.health_check_worker("worker-1")

        assert result is True

        # Verify worker state updated
        worker = registry.get_worker("worker-1")
        assert worker.status == WorkerStatus.AVAILABLE
        assert worker.health_check_failures == 0
        assert worker.last_health_check is not None
        assert worker.last_healthy_at is not None

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Async httpx mocking complex - covered in integration tests")
    async def test_health_check_worker_busy_status(self):
        """Test health check updates worker to busy when indicated."""
        registry = WorkerRegistry()

        # Register worker
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        # Mock health check with busy status
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "worker_status": "busy",
            "current_operation": "op-123",
        }

        # Patch httpx.AsyncClient.get at the module level
        with patch(
            "ktrdr.api.services.worker_registry.httpx.AsyncClient.get",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = mock_response
            result = await registry.health_check_worker("worker-1")

        assert result is True

        # Verify worker marked as busy
        worker = registry.get_worker("worker-1")
        assert worker.status == WorkerStatus.BUSY
        assert worker.current_operation_id == "op-123"

    @pytest.mark.asyncio
    async def test_health_check_worker_failure_increments_counter(self):
        """Test health check failure increments failure counter."""
        registry = WorkerRegistry()

        # Register worker
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        # Mock failed health check
        with patch("httpx.AsyncClient.get", side_effect=Exception("Connection error")):
            result = await registry.health_check_worker("worker-1")

        assert result is False

        # Verify failure counted
        worker = registry.get_worker("worker-1")
        assert worker.health_check_failures == 1
        assert worker.last_health_check is not None

    @pytest.mark.asyncio
    async def test_health_check_worker_marks_unavailable_after_threshold(self):
        """Test worker marked unavailable after 3 consecutive failures."""
        registry = WorkerRegistry()

        # Register worker
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        # Fail health check 3 times
        with patch("httpx.AsyncClient.get", side_effect=Exception("Connection error")):
            await registry.health_check_worker("worker-1")
            await registry.health_check_worker("worker-1")
            await registry.health_check_worker("worker-1")

        # Verify worker marked unavailable
        worker = registry.get_worker("worker-1")
        assert worker.status == WorkerStatus.TEMPORARILY_UNAVAILABLE
        assert worker.health_check_failures == 3

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Async httpx mocking complex - covered in integration tests")
    async def test_health_check_worker_resets_failures_on_success(self):
        """Test successful health check resets failure counter."""
        registry = WorkerRegistry()

        # Register worker
        worker = registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        # Manually set failures
        worker.health_check_failures = 2

        # Mock successful health check
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "worker_status": "idle",
        }

        # Patch httpx.AsyncClient.get at the module level
        with patch(
            "ktrdr.api.services.worker_registry.httpx.AsyncClient.get",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = mock_response
            result = await registry.health_check_worker("worker-1")

        assert result is True

        # Verify failures reset
        worker = registry.get_worker("worker-1")
        assert worker.health_check_failures == 0

    @pytest.mark.asyncio
    async def test_health_check_nonexistent_worker_returns_false(self):
        """Test health check on nonexistent worker returns False."""
        registry = WorkerRegistry()

        result = await registry.health_check_worker("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_handles_http_errors(self):
        """Test health check handles non-200 HTTP responses."""
        registry = WorkerRegistry()

        # Register worker
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        # Mock 500 error response
        mock_response = AsyncMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            result = await registry.health_check_worker("worker-1")

        assert result is False

        # Verify failure counted
        worker = registry.get_worker("worker-1")
        assert worker.health_check_failures == 1


class TestBackgroundHealthCheckTask:
    """Tests for background health check task lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_background_task(self):
        """Test start() creates background health check task."""
        registry = WorkerRegistry()

        # Initially no task
        assert registry._health_check_task is None

        # Start background task
        await registry.start()

        # Task should be created
        assert registry._health_check_task is not None
        assert not registry._health_check_task.done()

        # Cleanup
        await registry.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_background_task(self):
        """Test stop() cancels background health check task."""
        registry = WorkerRegistry()

        # Start task
        await registry.start()
        assert registry._health_check_task is not None

        # Stop task
        await registry.stop()

        # Task should be cancelled and cleared
        assert registry._health_check_task is None

    @pytest.mark.asyncio
    async def test_stop_without_task_is_safe(self):
        """Test stop() without running task doesn't raise error."""
        registry = WorkerRegistry()

        # Should not raise exception
        await registry.stop()

    @pytest.mark.asyncio
    async def test_start_twice_does_not_create_duplicate_task(self):
        """Test calling start() twice doesn't create duplicate tasks."""
        registry = WorkerRegistry()

        # Start first time
        await registry.start()
        first_task = registry._health_check_task

        # Start second time
        await registry.start()
        second_task = registry._health_check_task

        # Should be same task
        assert first_task is second_task

        # Cleanup
        await registry.stop()

    @pytest.mark.asyncio
    async def test_health_check_loop_runs_periodically(self):
        """Test background loop health checks all workers periodically."""
        registry = WorkerRegistry()
        registry._health_check_interval = 0.1  # Fast for testing

        # Register workers
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )
        registry.register_worker(
            worker_id="worker-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-2:5003",
        )

        # Track health check calls
        health_check_calls = []

        async def mock_health_check(worker_id):
            health_check_calls.append(worker_id)
            return True

        # Patch health_check_worker
        with patch.object(registry, "health_check_worker", side_effect=mock_health_check):
            # Start background task
            await registry.start()

            # Wait for at least one round of health checks
            await asyncio.sleep(0.2)

            # Stop background task
            await registry.stop()

        # Verify health checks were called for all workers
        assert "worker-1" in health_check_calls
        assert "worker-2" in health_check_calls

    @pytest.mark.asyncio
    async def test_health_check_loop_handles_exceptions(self):
        """Test background loop continues despite health check exceptions."""
        registry = WorkerRegistry()
        registry._health_check_interval = 0.1  # Fast for testing

        # Register worker
        registry.register_worker(
            worker_id="worker-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://worker-1:5003",
        )

        call_count = 0

        async def mock_health_check_with_error(worker_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First call fails")
            return True

        # Patch health_check_worker
        with patch.object(
            registry, "health_check_worker", side_effect=mock_health_check_with_error
        ):
            # Start background task
            await registry.start()

            # Wait for multiple rounds
            await asyncio.sleep(0.3)

            # Stop background task
            await registry.stop()

        # Verify loop continued after exception
        assert call_count >= 2
