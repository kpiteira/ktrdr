"""Unit tests for WorkerRegistry."""

from datetime import datetime

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
