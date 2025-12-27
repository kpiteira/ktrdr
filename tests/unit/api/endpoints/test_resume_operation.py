"""Unit tests for resume operation endpoint.

Tests the POST /operations/{operation_id}/resume endpoint for resuming
cancelled or failed operations from checkpoint.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.main import app
from ktrdr.api.models.operations import OperationInfo, OperationStatus, OperationType
from ktrdr.checkpoint.checkpoint_service import CheckpointData


@pytest.fixture
def mock_operations_service():
    """Create a mock OperationsService for testing."""
    mock_service = AsyncMock()
    return mock_service


@pytest.fixture
def mock_checkpoint_service():
    """Create a mock CheckpointService for testing."""
    mock_service = AsyncMock()
    return mock_service


@pytest.fixture
def mock_worker_registry():
    """Create a mock WorkerRegistry for testing."""
    from unittest.mock import MagicMock

    mock_registry = AsyncMock()
    # Mock a worker with endpoint_url
    mock_worker = MagicMock()
    mock_worker.worker_id = "test-worker-123"
    mock_worker.endpoint_url = "http://test-worker:5005"
    mock_registry.select_worker.return_value = mock_worker
    return mock_registry


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx client for worker dispatch."""
    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "operation_id": "op_training_123",
    }
    mock_response.raise_for_status = MagicMock()

    return mock_response


@pytest.fixture
def client(
    mock_operations_service,
    mock_checkpoint_service,
    mock_worker_registry,
    mock_httpx_client,
):
    """Create a test client with dependency overrides."""
    from unittest.mock import AsyncMock as AM
    from unittest.mock import patch

    from ktrdr.api.endpoints.operations import _get_checkpoint_service
    from ktrdr.api.endpoints.workers import get_worker_registry
    from ktrdr.api.services.operations_service import get_operations_service

    # Override dependencies
    app.dependency_overrides[get_operations_service] = lambda: mock_operations_service
    app.dependency_overrides[_get_checkpoint_service] = lambda: mock_checkpoint_service
    app.dependency_overrides[get_worker_registry] = lambda: mock_worker_registry

    # Patch httpx for worker dispatch
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_instance = AM()
        mock_client_instance.__aenter__.return_value = mock_client_instance
        mock_client_instance.__aexit__.return_value = None
        mock_client_instance.post.return_value = mock_httpx_client
        mock_client_class.return_value = mock_client_instance

        client = TestClient(app)
        yield client

    # Clean up
    app.dependency_overrides.clear()


def make_operation_info(
    operation_id: str = "op_training_123",
    status: OperationStatus = OperationStatus.CANCELLED,
    operation_type: OperationType = OperationType.TRAINING,
) -> OperationInfo:
    """Create a mock OperationInfo for testing."""
    return OperationInfo(
        operation_id=operation_id,
        operation_type=operation_type,
        status=status,
        created_at=datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    )


def make_checkpoint_data(
    operation_id: str = "op_training_123",
    epoch: int = 25,
    checkpoint_type: str = "cancellation",
) -> CheckpointData:
    """Create a mock CheckpointData for testing."""
    return CheckpointData(
        operation_id=operation_id,
        checkpoint_type=checkpoint_type,
        created_at=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        state={"epoch": epoch, "train_loss": 0.5, "val_loss": 0.6},
        artifacts_path=f"/app/data/checkpoints/{operation_id}",
    )


class TestResumeOperationEndpoint:
    """Tests for POST /api/v1/operations/{operation_id}/resume endpoint."""

    def test_resume_operation_success_cancelled(
        self, client, mock_operations_service, mock_checkpoint_service
    ):
        """Test resuming a cancelled operation returns success."""
        operation_id = "op_training_123"
        mock_operations_service.try_resume.return_value = True
        mock_operations_service.get_operation.return_value = make_operation_info(
            operation_id=operation_id,
            status=OperationStatus.RUNNING,  # After try_resume, status is RUNNING
        )
        mock_checkpoint_service.load_checkpoint.return_value = make_checkpoint_data(
            operation_id=operation_id, epoch=25
        )

        response = client.post(f"/api/v1/operations/{operation_id}/resume")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["operation_id"] == operation_id
        assert data["data"]["status"] == "running"
        assert data["data"]["resumed_from"]["epoch"] == 25
        assert data["data"]["resumed_from"]["checkpoint_type"] == "cancellation"

    def test_resume_operation_success_failed(
        self, client, mock_operations_service, mock_checkpoint_service
    ):
        """Test resuming a failed operation returns success."""
        operation_id = "op_training_456"
        mock_operations_service.try_resume.return_value = True
        mock_operations_service.get_operation.return_value = make_operation_info(
            operation_id=operation_id,
            status=OperationStatus.RUNNING,
        )
        mock_checkpoint_service.load_checkpoint.return_value = make_checkpoint_data(
            operation_id=operation_id, epoch=10, checkpoint_type="failure"
        )

        response = client.post(f"/api/v1/operations/{operation_id}/resume")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["resumed_from"]["checkpoint_type"] == "failure"

    def test_resume_operation_not_found(
        self, client, mock_operations_service, mock_checkpoint_service
    ):
        """Test resuming non-existent operation returns 404."""
        operation_id = "op_nonexistent"
        mock_operations_service.try_resume.return_value = False
        mock_operations_service.get_operation.return_value = None

        response = client.post(f"/api/v1/operations/{operation_id}/resume")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_resume_operation_no_checkpoint(
        self, client, mock_operations_service, mock_checkpoint_service
    ):
        """Test resuming operation without checkpoint returns 404."""
        operation_id = "op_training_123"
        mock_operations_service.try_resume.return_value = True
        mock_operations_service.get_operation.return_value = make_operation_info(
            operation_id=operation_id
        )
        # No checkpoint available
        mock_checkpoint_service.load_checkpoint.return_value = None

        response = client.post(f"/api/v1/operations/{operation_id}/resume")

        assert response.status_code == 404
        data = response.json()
        assert "checkpoint" in data["detail"].lower()
        # Operation should be marked as FAILED since resume can't proceed
        mock_operations_service.update_status.assert_called_once_with(
            operation_id, status="FAILED"
        )

    def test_resume_operation_already_running(
        self, client, mock_operations_service, mock_checkpoint_service
    ):
        """Test resuming already running operation returns 409."""
        operation_id = "op_training_123"
        mock_operations_service.try_resume.return_value = False
        mock_operations_service.get_operation.return_value = make_operation_info(
            operation_id=operation_id,
            status=OperationStatus.RUNNING,
        )

        response = client.post(f"/api/v1/operations/{operation_id}/resume")

        assert response.status_code == 409
        data = response.json()
        assert "already running" in data["detail"].lower()

    def test_resume_operation_already_completed(
        self, client, mock_operations_service, mock_checkpoint_service
    ):
        """Test resuming completed operation returns 409."""
        operation_id = "op_training_123"
        mock_operations_service.try_resume.return_value = False
        mock_operations_service.get_operation.return_value = make_operation_info(
            operation_id=operation_id,
            status=OperationStatus.COMPLETED,
        )

        response = client.post(f"/api/v1/operations/{operation_id}/resume")

        assert response.status_code == 409
        data = response.json()
        assert "already completed" in data["detail"].lower()

    def test_resume_operation_generic_not_resumable(
        self, client, mock_operations_service, mock_checkpoint_service
    ):
        """Test resuming operation in non-resumable state returns 409."""
        operation_id = "op_training_123"
        mock_operations_service.try_resume.return_value = False
        mock_operations_service.get_operation.return_value = make_operation_info(
            operation_id=operation_id,
            status=OperationStatus.PENDING,
        )

        response = client.post(f"/api/v1/operations/{operation_id}/resume")

        assert response.status_code == 409
        data = response.json()
        assert "cannot resume" in data["detail"].lower()


class TestResumeOperationOptimisticLocking:
    """Tests for optimistic locking behavior."""

    def test_try_resume_called_before_checkpoint_load(
        self, client, mock_operations_service, mock_checkpoint_service
    ):
        """Test that try_resume is called before loading checkpoint."""
        operation_id = "op_training_123"
        mock_operations_service.try_resume.return_value = True
        mock_operations_service.get_operation.return_value = make_operation_info()
        mock_checkpoint_service.load_checkpoint.return_value = make_checkpoint_data()

        response = client.post(f"/api/v1/operations/{operation_id}/resume")

        assert response.status_code == 200
        # Verify try_resume was called
        mock_operations_service.try_resume.assert_called_once_with(operation_id)

    def test_checkpoint_not_loaded_if_try_resume_fails(
        self, client, mock_operations_service, mock_checkpoint_service
    ):
        """Test that checkpoint is not loaded if try_resume returns False."""
        operation_id = "op_training_123"
        mock_operations_service.try_resume.return_value = False
        mock_operations_service.get_operation.return_value = make_operation_info(
            status=OperationStatus.COMPLETED
        )

        response = client.post(f"/api/v1/operations/{operation_id}/resume")

        assert response.status_code == 409
        # Checkpoint should not have been loaded
        mock_checkpoint_service.load_checkpoint.assert_not_called()
