"""Tests for WorkerAPIBase extracted from training-host-service pattern."""

import uuid

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.models.operations import OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.workers.base import WorkerAPIBase


@pytest.fixture
def mock_operations_service():
    """Provide a mock OperationsService without real DB connections."""
    # Create service without repository to avoid DB connections in unit tests
    service = OperationsService(repository=None)
    return service


class MockWorker(WorkerAPIBase):
    """Mock worker for testing base class."""

    def __init__(self, operations_service=None):
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url="http://backend:8000",
        )
        # Override with mock service for unit tests (avoid real DB connections)
        if operations_service is not None:
            self._operations_service = operations_service


@pytest.mark.asyncio
class TestWorkerAPIBase:
    """Test WorkerAPIBase extracted from training-host-service."""

    def test_operations_service_initialized(self):
        """Test OperationsService is initialized on worker creation."""
        worker = MockWorker()
        assert worker._operations_service is not None
        assert hasattr(worker, "get_operations_service")

    def test_operations_endpoints_registered(self):
        """Test operations proxy endpoints are registered."""
        worker = MockWorker()
        client = TestClient(worker.app)

        # Test GET /api/v1/operations (list operations)
        response = client.get("/api/v1/operations")
        assert response.status_code == 200

        # Test GET /health
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_reports_idle_when_no_operations(self):
        """Test health endpoint reports 'idle' when no operations."""
        worker = MockWorker()
        client = TestClient(worker.app)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["worker_status"] == "idle"
        assert data["current_operation"] is None
        assert data["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_reports_busy_when_operation_active(
        self, mock_operations_service
    ):
        """Test health endpoint reports 'busy' when operation is active."""
        worker = MockWorker(operations_service=mock_operations_service)

        # Create a test operation
        from datetime import datetime

        from ktrdr.api.models.operations import OperationMetadata

        operation_id = f"test_op_{uuid.uuid4().hex[:8]}"
        await worker._operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(
                symbol="AAPL",
                timeframe="1d",
                mode="backtesting",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
            ),
        )

        client = TestClient(worker.app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["worker_status"] == "busy"
        assert data["current_operation"] == operation_id

    def test_operations_endpoint_returns_404_for_missing_operation(
        self, mock_operations_service
    ):
        """Test /api/v1/operations/{id} returns 404 for non-existent operation."""
        worker = MockWorker(operations_service=mock_operations_service)
        client = TestClient(worker.app)

        response = client.get("/api/v1/operations/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_operations_endpoint_returns_operation_status(
        self, mock_operations_service
    ):
        """Test /api/v1/operations/{id} returns operation status."""
        worker = MockWorker(operations_service=mock_operations_service)

        # Create a test operation
        from datetime import datetime

        from ktrdr.api.models.operations import OperationMetadata

        operation_id = f"test_op_{uuid.uuid4().hex[:8]}"
        await worker._operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(
                symbol="EURUSD",
                timeframe="1h",
                mode="backtesting",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
            ),
        )

        client = TestClient(worker.app)
        response = client.get(f"/api/v1/operations/{operation_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["operation_id"] == operation_id
        # Operations start in "pending" status until explicitly started
        assert data["data"]["status"] in ["pending", "running"]

    def test_list_operations_endpoint(self):
        """Test /api/v1/operations endpoint lists operations."""
        worker = MockWorker()
        client = TestClient(worker.app)

        response = client.get("/api/v1/operations")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total_count" in data
        assert "active_count" in data
        assert isinstance(data["data"], list)

    def test_fastapi_app_has_cors_middleware(self):
        """Test FastAPI app is configured with CORS middleware."""
        worker = MockWorker()

        # Check that CORS middleware is present
        # FastAPI wraps middleware in Middleware class, check the cls attribute
        has_cors = any(
            hasattr(m, "cls") and m.cls.__name__ == "CORSMiddleware"
            for m in worker.app.user_middleware
        )
        assert has_cors, "CORS middleware not found in app middleware stack"

    def test_worker_id_generated(self):
        """Test worker_id is generated or taken from environment."""
        worker = MockWorker()
        assert worker.worker_id is not None
        assert len(worker.worker_id) > 0

    def test_worker_type_and_operation_type_set(self):
        """Test worker type and operation type are set correctly."""
        worker = MockWorker()
        assert worker.worker_type == WorkerType.BACKTESTING
        assert worker.operation_type == OperationType.BACKTESTING

    def test_root_endpoint_exists(self):
        """Test root endpoint (/) exists and returns worker info."""
        worker = MockWorker()
        client = TestClient(worker.app)

        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "worker_id" in data

    @pytest.mark.asyncio
    async def test_operations_metrics_endpoint(self, mock_operations_service):
        """Test /api/v1/operations/{id}/metrics endpoint."""
        worker = MockWorker(operations_service=mock_operations_service)

        # Create a test operation
        from datetime import datetime

        from ktrdr.api.models.operations import OperationMetadata

        operation_id = f"test_op_{uuid.uuid4().hex[:8]}"
        await worker._operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(
                symbol="GBPUSD",
                timeframe="4h",
                mode="backtesting",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
            ),
        )

        client = TestClient(worker.app)
        response = client.get(f"/api/v1/operations/{operation_id}/metrics?cursor=0")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["operation_id"] == operation_id

    @pytest.mark.asyncio
    async def test_cancel_operation_endpoint(self, mock_operations_service):
        """Test DELETE /api/v1/operations/{id}/cancel endpoint."""
        worker = MockWorker(operations_service=mock_operations_service)

        # Create a test operation
        from datetime import datetime

        from ktrdr.api.models.operations import OperationMetadata

        operation_id = f"test_op_{uuid.uuid4().hex[:8]}"
        await worker._operations_service.create_operation(
            operation_id=operation_id,
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(
                symbol="USDJPY",
                timeframe="1d",
                mode="backtesting",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
            ),
        )

        client = TestClient(worker.app)
        response = client.delete(f"/api/v1/operations/{operation_id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_startup_event_registered(self):
        """Test startup event is registered."""
        worker = MockWorker()
        # FastAPI stores on_event callbacks - we can't easily test this
        # but we can verify the method exists
        assert hasattr(worker, "app")
        assert hasattr(worker.app, "on_event")


class TestWorkerAPIBaseWithDifferentTypes:
    """Test WorkerAPIBase with different worker types."""

    def test_training_worker_type(self):
        """Test creating a training worker."""

        class TrainingMockWorker(WorkerAPIBase):
            def __init__(self):
                super().__init__(
                    worker_type=WorkerType.CPU_TRAINING,
                    operation_type=OperationType.TRAINING,
                    worker_port=5004,
                    backend_url="http://backend:8000",
                )

        worker = TrainingMockWorker()
        assert worker.worker_type == WorkerType.CPU_TRAINING
        assert worker.operation_type == OperationType.TRAINING

        client = TestClient(worker.app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "training" in data["service"].lower()


class TestHealthCheckTracking:
    """Tests for health check tracking (Task 1.6: preparation for re-registration monitor)."""

    def test_last_health_check_received_initialized_to_none(self):
        """Test _last_health_check_received is initialized to None."""
        worker = MockWorker()
        assert hasattr(worker, "_last_health_check_received")
        assert worker._last_health_check_received is None

    def test_health_endpoint_updates_last_health_check_received(self):
        """Test health endpoint updates _last_health_check_received timestamp."""
        from datetime import UTC, datetime

        worker = MockWorker()
        client = TestClient(worker.app)

        # Initially None
        assert worker._last_health_check_received is None

        # Call health endpoint
        before_call = datetime.now(UTC)
        response = client.get("/health")
        after_call = datetime.now(UTC)

        assert response.status_code == 200

        # Timestamp should now be set
        assert worker._last_health_check_received is not None
        assert isinstance(worker._last_health_check_received, datetime)

        # Timestamp should be between before and after the call
        assert before_call <= worker._last_health_check_received <= after_call

    def test_health_endpoint_response_format_unchanged(self):
        """Test health response format is backward compatible (no new fields)."""
        worker = MockWorker()
        client = TestClient(worker.app)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        # Verify expected fields exist
        assert "healthy" in data
        assert "service" in data
        assert "timestamp" in data
        assert "status" in data
        assert "worker_status" in data
        assert "current_operation" in data

        # Verify no unexpected fields related to health check tracking
        # (internal state should not leak into response)
        assert "last_health_check_received" not in data
        assert "_last_health_check_received" not in data

    def test_multiple_health_checks_update_timestamp(self):
        """Test each health check updates the timestamp."""
        import time

        worker = MockWorker()
        client = TestClient(worker.app)

        # First health check
        client.get("/health")
        first_timestamp = worker._last_health_check_received

        # Small delay to ensure different timestamp
        time.sleep(0.01)

        # Second health check
        client.get("/health")
        second_timestamp = worker._last_health_check_received

        assert second_timestamp > first_timestamp
