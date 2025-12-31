"""Unit tests for workers API endpoint."""

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.endpoints.workers import get_worker_registry
from ktrdr.api.main import app
from ktrdr.api.models.workers import WorkerStatus, WorkerType
from ktrdr.api.services.worker_registry import WorkerRegistry


@pytest.fixture
def worker_registry():
    """Create a fresh WorkerRegistry for each test."""
    return WorkerRegistry()


@pytest.fixture
def client(worker_registry):
    """Create a test client with dependency overrides."""
    # Override the get_worker_registry dependency
    app.dependency_overrides[get_worker_registry] = lambda: worker_registry

    client = TestClient(app)
    yield client

    # Clean up dependency overrides
    app.dependency_overrides.clear()


class TestWorkerRegistrationEndpoint:
    """Tests for POST /api/v1/workers/register endpoint."""

    def test_register_new_worker(self, client, worker_registry):
        """Test registering a new worker."""
        # Register a worker
        response = client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "backtest-1",
                "worker_type": "backtesting",
                "endpoint_url": "http://192.168.1.201:5003",
                "capabilities": {"cores": 4, "memory_gb": 8},
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["worker_id"] == "backtest-1"
        assert data["worker_type"] == "backtesting"
        assert data["endpoint_url"] == "http://192.168.1.201:5003"
        assert data["status"] == "available"
        assert data["capabilities"] == {"cores": 4, "memory_gb": 8}
        assert data["last_healthy_at"] is not None

    def test_register_worker_without_capabilities(self, client, worker_registry):
        """Test registering a worker without capabilities."""
        response = client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "backtest-2",
                "worker_type": "backtesting",
                "endpoint_url": "http://192.168.1.202:5003",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["worker_id"] == "backtest-2"
        assert data["capabilities"] == {}

    def test_register_worker_idempotent(self, client, worker_registry):
        """Test that re-registering a worker updates it."""
        # Register worker first time
        client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "backtest-1",
                "worker_type": "backtesting",
                "endpoint_url": "http://192.168.1.201:5003",
            },
        )

        # Re-register with different URL
        response2 = client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "backtest-1",
                "worker_type": "backtesting",
                "endpoint_url": "http://192.168.1.201:5555",
            },
        )

        assert response2.status_code == 200
        data = response2.json()
        assert data["endpoint_url"] == "http://192.168.1.201:5555"

        # Verify only one worker in registry
        workers = worker_registry.list_workers()
        assert len(workers) == 1

    def test_register_worker_invalid_type(self, client, worker_registry):
        """Test registering a worker with invalid worker_type."""
        response = client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "invalid-1",
                "worker_type": "invalid_type",  # Not a valid WorkerType
                "endpoint_url": "http://192.168.1.201:5003",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_register_worker_missing_required_fields(self, client, worker_registry):
        """Test registering a worker with missing required fields."""
        # Missing worker_id
        response = client.post(
            "/api/v1/workers/register",
            json={
                "worker_type": "backtesting",
                "endpoint_url": "http://192.168.1.201:5003",
            },
        )

        assert response.status_code == 422


class TestListWorkersEndpoint:
    """Tests for GET /api/v1/workers endpoint."""

    @pytest.mark.asyncio
    async def test_list_all_workers(self, client, worker_registry):
        """Test listing all registered workers."""
        # Pre-register some workers
        await worker_registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://192.168.1.201:5003",
        )
        await worker_registry.register_worker(
            worker_id="training-1",
            worker_type=WorkerType.CPU_TRAINING,
            endpoint_url="http://192.168.1.202:5004",
        )

        response = client.get("/api/v1/workers")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 2
        worker_ids = {w["worker_id"] for w in data}
        assert worker_ids == {"backtest-1", "training-1"}

    @pytest.mark.asyncio
    async def test_list_workers_filter_by_type(self, client, worker_registry):
        """Test listing workers filtered by type."""
        await worker_registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://192.168.1.201:5003",
        )
        await worker_registry.register_worker(
            worker_id="backtest-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://192.168.1.202:5003",
        )
        await worker_registry.register_worker(
            worker_id="training-1",
            worker_type=WorkerType.CPU_TRAINING,
            endpoint_url="http://192.168.1.203:5004",
        )

        response = client.get("/api/v1/workers?worker_type=backtesting")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 2
        worker_ids = {w["worker_id"] for w in data}
        assert worker_ids == {"backtest-1", "backtest-2"}

    @pytest.mark.asyncio
    async def test_list_workers_filter_by_status(self, client, worker_registry):
        """Test listing workers filtered by status."""
        await worker_registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://192.168.1.201:5003",
        )
        result = await worker_registry.register_worker(
            worker_id="backtest-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://192.168.1.202:5003",
        )

        # Manually set one worker to BUSY
        result.worker.status = WorkerStatus.BUSY

        response = client.get("/api/v1/workers?status=available")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["worker_id"] == "backtest-1"

    def test_list_workers_empty_registry(self, client, worker_registry):
        """Test listing workers when registry is empty."""
        response = client.get("/api/v1/workers")

        assert response.status_code == 200
        data = response.json()

        assert data == []


class TestGetWorkerEndpoint:
    """Tests for GET /api/v1/workers/{worker_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_worker_found(self, client, worker_registry):
        """Test getting a worker that exists."""
        # Pre-register a worker
        await worker_registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://192.168.1.201:5003",
            capabilities={"cores": 4},
        )

        response = client.get("/api/v1/workers/backtest-1")

        assert response.status_code == 200
        data = response.json()
        assert data["worker_id"] == "backtest-1"
        assert data["worker_type"] == "backtesting"
        assert data["endpoint_url"] == "http://192.168.1.201:5003"
        assert data["capabilities"] == {"cores": 4}

    def test_get_worker_not_found(self, client, worker_registry):
        """Test getting a worker that doesn't exist returns 404."""
        response = client.get("/api/v1/workers/nonexistent-worker")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_worker_after_registration(self, client, worker_registry):
        """Test that a worker can be retrieved immediately after registration."""
        # Register via endpoint
        client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "training-1",
                "worker_type": "training",
                "endpoint_url": "http://192.168.1.202:5004",
            },
        )

        # Retrieve via GET endpoint
        response = client.get("/api/v1/workers/training-1")

        assert response.status_code == 200
        data = response.json()
        assert data["worker_id"] == "training-1"


class TestWorkerRegistrationWithResilience:
    """Tests for worker registration with resilience fields (M1 checkpoint)."""

    def test_register_worker_with_current_operation(self, client, worker_registry):
        """Test registering a worker that reports a current operation."""
        response = client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "training-1",
                "worker_type": "training",
                "endpoint_url": "http://192.168.1.201:5004",
                "current_operation_id": "op_training_123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["worker_id"] == "training-1"
        # Note: The endpoint doesn't return current_operation_id in response,
        # but it should accept it without error

    def test_register_worker_with_completed_operations(self, client, worker_registry):
        """Test registering a worker that reports completed operations."""
        response = client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "training-2",
                "worker_type": "training",
                "endpoint_url": "http://192.168.1.202:5004",
                "completed_operations": [
                    {
                        "operation_id": "op_completed_1",
                        "status": "COMPLETED",
                        "result": {"accuracy": 0.95},
                        "completed_at": "2024-01-15T10:30:00Z",
                    },
                    {
                        "operation_id": "op_failed_1",
                        "status": "FAILED",
                        "error_message": "Out of memory",
                        "completed_at": "2024-01-15T11:00:00Z",
                    },
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["worker_id"] == "training-2"

    def test_register_worker_with_all_resilience_fields(self, client, worker_registry):
        """Test registering a worker with all new resilience fields."""
        response = client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "training-3",
                "worker_type": "training",
                "endpoint_url": "http://192.168.1.203:5004",
                "capabilities": {"gpu": True, "memory_gb": 16},
                "current_operation_id": "op_running_456",
                "completed_operations": [
                    {
                        "operation_id": "op_done_1",
                        "status": "COMPLETED",
                        "result": {"model_path": "/models/v1.pt"},
                        "completed_at": "2024-01-15T09:00:00Z",
                    },
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["worker_id"] == "training-3"
        assert data["capabilities"] == {"gpu": True, "memory_gb": 16}

    def test_register_worker_backward_compatible(self, client, worker_registry):
        """Test that registration still works without new fields (backward compatible)."""
        # This is essentially the same as existing tests, but explicit about backward compatibility
        response = client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "backtest-compat",
                "worker_type": "backtesting",
                "endpoint_url": "http://192.168.1.204:5003",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["worker_id"] == "backtest-compat"

    def test_register_worker_invalid_completed_operation_status(
        self, client, worker_registry
    ):
        """Test that invalid status in completed_operations is rejected."""
        response = client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "training-invalid",
                "worker_type": "training",
                "endpoint_url": "http://192.168.1.205:5004",
                "completed_operations": [
                    {
                        "operation_id": "op_bad",
                        "status": "RUNNING",  # Invalid - not a terminal status
                        "completed_at": "2024-01-15T10:30:00Z",
                    },
                ],
            },
        )

        # Should fail validation
        assert response.status_code == 422


class TestShutdownModeEndpoint:
    """Tests for registration rejection during shutdown (M7.5 Task 7.5.3)."""

    def test_register_rejected_during_shutdown(self, client, worker_registry):
        """Test that registration returns 503 when backend is shutting down."""
        # Put registry in shutdown mode
        worker_registry.begin_shutdown()

        # Try to register a worker
        response = client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "backtest-1",
                "worker_type": "backtesting",
                "endpoint_url": "http://192.168.1.201:5003",
            },
        )

        assert response.status_code == 503
        assert "shutting down" in response.json()["detail"].lower()
        assert response.headers.get("Retry-After") == "5"

    def test_register_succeeds_before_shutdown(self, client, worker_registry):
        """Test that registration works normally before shutdown mode."""
        # Verify not in shutdown mode
        assert not worker_registry.is_shutting_down()

        response = client.post(
            "/api/v1/workers/register",
            json={
                "worker_id": "backtest-1",
                "worker_type": "backtesting",
                "endpoint_url": "http://192.168.1.201:5003",
            },
        )

        assert response.status_code == 200
