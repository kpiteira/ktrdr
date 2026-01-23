"""
Integration tests for Operations API endpoints.

Tests the operations endpoints with mocked service dependencies.
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
    service_mock = AsyncMock()

    # Mock list_operations to return empty list
    service_mock.list_operations.return_value = ([], 0, 0)

    # Mock get_operation to return None for nonexistent operations
    service_mock.get_operation.return_value = None

    # Mock cancel_operation to return False for nonexistent operations
    service_mock.cancel_operation.return_value = False

    # Mock retry_operation to return None for nonexistent operations
    service_mock.retry_operation.return_value = None

    return service_mock


@pytest.fixture
def client_with_mocked_ops(client, mock_operations_service):
    """Create a test client with mocked operations service dependency."""
    from ktrdr.api.dependencies import get_operations_service

    # Override the operations service dependency
    client.app.dependency_overrides[get_operations_service] = (
        lambda: mock_operations_service
    )

    yield client

    # Clean up after test
    client.app.dependency_overrides.clear()


class TestOperationsEndpoints:
    """Test operations API endpoints."""

    @pytest.mark.api
    def test_list_operations_success(self, client_with_mocked_ops):
        """Test listing operations successfully."""
        response = client_with_mocked_ops.get("/api/v1/operations")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "total_count" in data
        assert "active_count" in data
        assert isinstance(data["data"], list)

    @pytest.mark.api
    def test_list_operations_with_filters(self, client_with_mocked_ops):
        """Test listing operations with status filter."""
        response = client_with_mocked_ops.get(
            "/api/v1/operations?status=completed&limit=10"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    @pytest.mark.api
    def test_list_operations_active_only(self, client_with_mocked_ops):
        """Test listing only active operations."""
        response = client_with_mocked_ops.get("/api/v1/operations?active_only=true")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    @pytest.mark.api
    def test_get_operation_status_not_found(self, client_with_mocked_ops):
        """Test getting status for non-existent operation."""
        response = client_with_mocked_ops.get(
            "/api/v1/operations/nonexistent_operation_id"
        )

        assert response.status_code == 404

    @pytest.mark.api
    def test_cancel_operation_not_found(self, client_with_mocked_ops):
        """Test cancelling non-existent operation."""
        response = client_with_mocked_ops.delete(
            "/api/v1/operations/nonexistent_operation_id"
        )

        assert response.status_code == 404

    @pytest.mark.api
    def test_retry_operation_not_found(self, client_with_mocked_ops):
        """Test retrying non-existent operation."""
        response = client_with_mocked_ops.post(
            "/api/v1/operations/nonexistent_operation_id/retry"
        )

        assert response.status_code == 404

    @pytest.mark.api
    def test_list_operations_pagination(self, client_with_mocked_ops):
        """Test operations list pagination parameters."""
        response = client_with_mocked_ops.get("/api/v1/operations?limit=5&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) <= 5

    @pytest.mark.api
    def test_list_operations_by_type(self, client_with_mocked_ops):
        """Test filtering operations by type."""
        response = client_with_mocked_ops.get(
            "/api/v1/operations?operation_type=data_load"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    @pytest.mark.api
    def test_cancel_operation_simple(self, client_with_mocked_ops):
        """Test cancelling operation."""
        response = client_with_mocked_ops.delete("/api/v1/operations/test_operation")

        # Should return 404 since operation doesn't exist
        assert response.status_code == 404

    @pytest.mark.api
    def test_cancel_nonexistent_operation(self, client_with_mocked_ops):
        """Test cancelling non-existent operation."""
        response = client_with_mocked_ops.delete(
            "/api/v1/operations/definitely_nonexistent_operation"
        )

        # Should return 404 since operation doesn't exist
        assert response.status_code == 404
