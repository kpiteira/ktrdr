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

    def test_list_all_workers(self, client, worker_registry):
        """Test listing all registered workers."""
        # Pre-register some workers
        worker_registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://192.168.1.201:5003",
        )
        worker_registry.register_worker(
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

    def test_list_workers_filter_by_type(self, client, worker_registry):
        """Test listing workers filtered by type."""
        worker_registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://192.168.1.201:5003",
        )
        worker_registry.register_worker(
            worker_id="backtest-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://192.168.1.202:5003",
        )
        worker_registry.register_worker(
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

    def test_list_workers_filter_by_status(self, client, worker_registry):
        """Test listing workers filtered by status."""
        worker_registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://192.168.1.201:5003",
        )
        worker2 = worker_registry.register_worker(
            worker_id="backtest-2",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://192.168.1.202:5003",
        )

        # Manually set one worker to BUSY
        worker2.status = WorkerStatus.BUSY

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
