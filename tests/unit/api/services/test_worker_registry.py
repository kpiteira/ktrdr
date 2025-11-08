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
