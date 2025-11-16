"""
Unit tests for Checkpoint Management API endpoints.

Tests the DELETE /api/v1/operations/{operation_id}/checkpoint endpoint
and related checkpoint cleanup endpoints.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def mock_operations_service():
    """Create a mock OperationsService for testing endpoints."""
    mock_instance = AsyncMock()
    return mock_instance


@pytest.fixture
def mock_checkpoint_service():
    """Create a mock CheckpointService for testing endpoints."""
    mock_instance = AsyncMock()
    mock_instance.delete_checkpoint = AsyncMock()
    return mock_instance


@pytest.fixture
def client_with_mocked_services(
    client, mock_operations_service, mock_checkpoint_service
):
    """Create a test client with mocked services."""
    from ktrdr.api.dependencies import get_checkpoint_service, get_operations_service

    # Override the dependencies
    client.app.dependency_overrides[get_operations_service] = (
        lambda: mock_operations_service
    )
    client.app.dependency_overrides[get_checkpoint_service] = (
        lambda: mock_checkpoint_service
    )

    yield client

    # Clean up
    client.app.dependency_overrides.clear()


class TestDeleteCheckpointEndpoint:
    """Test DELETE /api/v1/operations/{operation_id}/checkpoint endpoint."""

    @pytest.mark.api
    def test_delete_checkpoint_success(
        self,
        client_with_mocked_services,
        mock_operations_service,
        mock_checkpoint_service,
    ):
        """Test successfully deleting a checkpoint."""
        # Mock operation exists and has checkpoint
        mock_operation = AsyncMock()
        mock_operation.operation_id = "op_training_001"
        mock_operations_service.get_operation.return_value = mock_operation

        # Mock successful checkpoint deletion
        mock_checkpoint_service.delete_checkpoint.return_value = (
            None  # Returns None on success
        )

        # Call endpoint
        response = client_with_mocked_services.delete(
            "/api/v1/operations/op_training_001/checkpoint"
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"] == "op_training_001"
        assert "deleted" in data["message"].lower()

        # Verify services were called
        mock_operations_service.get_operation.assert_called_once_with("op_training_001")
        mock_checkpoint_service.delete_checkpoint.assert_called_once_with(
            "op_training_001"
        )

    @pytest.mark.api
    def test_delete_checkpoint_operation_not_found(
        self, client_with_mocked_services, mock_operations_service
    ):
        """Test delete fails when operation doesn't exist."""
        # Mock operation not found
        mock_operations_service.get_operation.return_value = None

        # Call endpoint
        response = client_with_mocked_services.delete(
            "/api/v1/operations/op_nonexistent/checkpoint"
        )

        # Should return 404
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.api
    def test_delete_checkpoint_no_checkpoint_exists(
        self,
        client_with_mocked_services,
        mock_operations_service,
        mock_checkpoint_service,
    ):
        """Test delete when no checkpoint exists for operation."""
        # Mock operation exists
        mock_operation = AsyncMock()
        mock_operation.operation_id = "op_training_001"
        mock_operations_service.get_operation.return_value = mock_operation

        # Mock no checkpoint found (checkpoint service returns without error but nothing to delete)
        mock_checkpoint_service.delete_checkpoint.return_value = None

        # Call endpoint
        response = client_with_mocked_services.delete(
            "/api/v1/operations/op_training_001/checkpoint"
        )

        # Should succeed (idempotent)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.api
    def test_delete_checkpoint_internal_error(
        self,
        client_with_mocked_services,
        mock_operations_service,
        mock_checkpoint_service,
    ):
        """Test delete handles internal errors gracefully."""
        # Mock operation exists
        mock_operation = AsyncMock()
        mock_operation.operation_id = "op_training_001"
        mock_operations_service.get_operation.return_value = mock_operation

        # Mock checkpoint service error
        mock_checkpoint_service.delete_checkpoint.side_effect = Exception(
            "Database connection lost"
        )

        # Call endpoint
        response = client_with_mocked_services.delete(
            "/api/v1/operations/op_training_001/checkpoint"
        )

        # Should return 500
        assert response.status_code == 500
        data = response.json()
        assert "error" in data["detail"].lower() or "failed" in data["detail"].lower()


class TestCheckpointCleanupEndpoints:
    """Test checkpoint cleanup endpoints."""

    @pytest.mark.api
    def test_cleanup_cancelled_checkpoints(
        self,
        client_with_mocked_services,
        mock_operations_service,
        mock_checkpoint_service,
    ):
        """Test cleanup of cancelled operation checkpoints."""
        # Mock finding cancelled operations with checkpoints
        cancelled_ops = [
            AsyncMock(operation_id="op_001", status="CANCELLED"),
            AsyncMock(operation_id="op_002", status="CANCELLED"),
        ]
        mock_operations_service.load_operations_with_checkpoints.return_value = (
            cancelled_ops
        )

        # Mock checkpoint deletions
        mock_checkpoint_service.delete_checkpoint.return_value = None

        # Call endpoint
        response = client_with_mocked_services.post(
            "/api/v1/operations/checkpoints/cleanup-cancelled"
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 2
        assert "op_001" in data["operation_ids"]
        assert "op_002" in data["operation_ids"]

    @pytest.mark.api
    def test_cleanup_old_checkpoints(
        self,
        client_with_mocked_services,
        mock_operations_service,
        mock_checkpoint_service,
    ):
        """Test cleanup of old checkpoints."""
        # Mock finding old operations with checkpoints
        old_ops = [
            AsyncMock(operation_id="op_old_001", status="FAILED"),
            AsyncMock(operation_id="op_old_002", status="FAILED"),
            AsyncMock(operation_id="op_old_003", status="CANCELLED"),
        ]
        mock_operations_service.load_operations_with_checkpoints.return_value = old_ops

        # Mock checkpoint deletions
        mock_checkpoint_service.delete_checkpoint.return_value = None

        # Call endpoint with days parameter
        response = client_with_mocked_services.post(
            "/api/v1/operations/checkpoints/cleanup-old?days=7"
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 3
        assert len(data["operation_ids"]) == 3

    @pytest.mark.api
    def test_cleanup_old_checkpoints_default_days(
        self,
        client_with_mocked_services,
        mock_operations_service,
        mock_checkpoint_service,
    ):
        """Test cleanup old uses default of 30 days."""
        # Mock no old operations
        mock_operations_service.load_operations_with_checkpoints.return_value = []

        # Call endpoint without days parameter
        response = client_with_mocked_services.post(
            "/api/v1/operations/checkpoints/cleanup-old"
        )

        # Should succeed with default
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 0

    @pytest.mark.api
    def test_cleanup_no_checkpoints_found(
        self, client_with_mocked_services, mock_operations_service
    ):
        """Test cleanup when no checkpoints exist to clean."""
        # Mock no operations with checkpoints
        mock_operations_service.load_operations_with_checkpoints.return_value = []

        # Call cleanup-cancelled endpoint
        response = client_with_mocked_services.post(
            "/api/v1/operations/checkpoints/cleanup-cancelled"
        )

        # Should succeed with zero count
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 0
        assert data["operation_ids"] == []
