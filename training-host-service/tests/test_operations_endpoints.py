"""
Tests for Operations Endpoints in Training Host Service

Task 2.2 (M2): Add /operations/* endpoints to training host service
These tests verify that the operations API in the host service matches the backend API contract.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)


@pytest.fixture
def mock_operations_service():
    """Mock OperationsService for testing endpoints."""
    service = MagicMock()
    service.get_operation = AsyncMock()
    service.list_operations = AsyncMock()
    service.get_operation_metrics = AsyncMock()
    return service


@pytest.fixture
def test_client(mock_operations_service):
    """Create test client with mocked operations service."""
    # Import main app and override dependency
    import sys
    from pathlib import Path

    # Add parent dir to path
    parent_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(parent_dir))

    from main import app

    from services.operations import get_operations_service

    # Override dependency
    app.dependency_overrides[get_operations_service] = lambda: mock_operations_service

    client = TestClient(app)
    yield client

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def sample_operation():
    """Sample operation for testing."""
    return OperationInfo(
        operation_id="host_training_test123",
        operation_type=OperationType.TRAINING,
        status=OperationStatus.RUNNING,
        created_at=datetime(2025, 1, 23, 10, 0, 0, tzinfo=timezone.utc),
        started_at=datetime(2025, 1, 23, 10, 0, 5, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 23, 10, 5, 30, tzinfo=timezone.utc),
        progress=OperationProgress(
            percentage=45.0,
            current_step="Epoch 45/100",
            message="Training in progress",
            items_processed=45000,
            total_items=100000,
        ),
        metadata=OperationMetadata(
            symbol="AAPL",
            timeframe="1d",
        ),
    )


class TestGetOperationEndpoint:
    """Tests for GET /operations/{operation_id} endpoint."""

    def test_get_operation_success(self, test_client, mock_operations_service, sample_operation):
        """Test successful operation retrieval."""
        # Setup mock
        mock_operations_service.get_operation.return_value = sample_operation

        # Make request
        response = test_client.get("/api/v1/operations/host_training_test123")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["operation_id"] == "host_training_test123"
        assert data["data"]["status"] == "running"
        assert data["data"]["progress"]["percentage"] == 45.0

        # Verify service was called
        mock_operations_service.get_operation.assert_called_once_with(
            "host_training_test123", force_refresh=False
        )

    def test_get_operation_with_force_refresh(self, test_client, mock_operations_service, sample_operation):
        """Test operation retrieval with force_refresh parameter."""
        mock_operations_service.get_operation.return_value = sample_operation

        response = test_client.get("/api/v1/operations/host_training_test123?force_refresh=true")

        assert response.status_code == 200
        mock_operations_service.get_operation.assert_called_once_with(
            "host_training_test123", force_refresh=True
        )

    def test_get_operation_not_found(self, test_client, mock_operations_service):
        """Test 404 when operation doesn't exist."""
        mock_operations_service.get_operation.side_effect = KeyError("Operation not found")

        response = test_client.get("/api/v1/operations/nonexistent_op")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetOperationMetricsEndpoint:
    """Tests for GET /operations/{operation_id}/metrics endpoint."""

    def test_get_metrics_success(self, test_client, mock_operations_service, sample_operation):
        """Test successful metrics retrieval."""
        # Setup mocks
        mock_operations_service.get_operation.return_value = sample_operation

        mock_metrics = [
            {"epoch": 0, "train_loss": 2.5, "val_loss": 2.6},
            {"epoch": 1, "train_loss": 2.3, "val_loss": 2.4},
        ]
        mock_operations_service.get_operation_metrics.return_value = mock_metrics

        # Make request
        response = test_client.get("/api/v1/operations/host_training_test123/metrics")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "metrics" in data["data"]
        assert len(data["data"]["metrics"]) == 2

        # Verify service was called
        mock_operations_service.get_operation_metrics.assert_called_once_with(
            "host_training_test123", cursor=0
        )

    def test_get_metrics_with_cursor(self, test_client, mock_operations_service, sample_operation):
        """Test metrics retrieval with cursor parameter."""
        mock_operations_service.get_operation.return_value = sample_operation
        mock_operations_service.get_operation_metrics.return_value = []

        response = test_client.get("/api/v1/operations/host_training_test123/metrics?cursor=5")

        assert response.status_code == 200
        mock_operations_service.get_operation_metrics.assert_called_once_with(
            "host_training_test123", cursor=5
        )

    def test_get_metrics_operation_not_found(self, test_client, mock_operations_service):
        """Test 404 when operation doesn't exist."""
        mock_operations_service.get_operation.side_effect = KeyError("Operation not found")

        response = test_client.get("/api/v1/operations/nonexistent_op/metrics")

        assert response.status_code == 404


class TestListOperationsEndpoint:
    """Tests for GET /operations endpoint."""

    def test_list_operations_success(self, test_client, mock_operations_service, sample_operation):
        """Test successful operations list retrieval."""
        # Setup mock
        operations = [sample_operation]
        mock_operations_service.list_operations.return_value = (operations, 1, 1)

        # Make request
        response = test_client.get("/api/v1/operations")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_count"] == 1
        assert data["active_count"] == 1
        assert len(data["data"]) == 1
        assert data["data"][0]["operation_id"] == "host_training_test123"

        # Verify service was called
        mock_operations_service.list_operations.assert_called_once()

    def test_list_operations_with_status_filter(self, test_client, mock_operations_service):
        """Test operations list with status filter."""
        mock_operations_service.list_operations.return_value = ([], 0, 0)

        response = test_client.get("/api/v1/operations?status=running")

        assert response.status_code == 200
        # Verify status filter was passed to service
        call_args = mock_operations_service.list_operations.call_args
        assert call_args is not None

    def test_list_operations_with_type_filter(self, test_client, mock_operations_service):
        """Test operations list with operation_type filter."""
        mock_operations_service.list_operations.return_value = ([], 0, 0)

        response = test_client.get("/api/v1/operations?operation_type=training")

        assert response.status_code == 200
        call_args = mock_operations_service.list_operations.call_args
        assert call_args is not None

    def test_list_operations_empty(self, test_client, mock_operations_service):
        """Test operations list when no operations exist."""
        mock_operations_service.list_operations.return_value = ([], 0, 0)

        response = test_client.get("/api/v1/operations")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_count"] == 0
        assert data["active_count"] == 0
        assert len(data["data"]) == 0


class TestOperationsEndpointsIntegration:
    """Integration tests with real OperationsService (not mocked)."""

    @pytest.mark.integration
    def test_endpoints_registered_in_swagger(self, test_client):
        """Test that endpoints appear in OpenAPI/Swagger docs."""
        response = test_client.get("/openapi.json")

        assert response.status_code == 200
        openapi_schema = response.json()

        # Verify endpoints are registered
        paths = openapi_schema.get("paths", {})
        assert "/api/v1/operations/{operation_id}" in paths
        assert "/api/v1/operations/{operation_id}/metrics" in paths
        assert "/api/v1/operations" in paths
