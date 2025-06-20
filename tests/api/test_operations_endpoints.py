"""
Unit tests for Operations API endpoints - simplified approach.

Tests the operations endpoints with real service functionality.
"""

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


class TestOperationsEndpoints:
    """Test operations API endpoints."""

    @pytest.mark.api
    def test_list_operations_success(self, client):
        """Test listing operations successfully."""
        response = client.get("/api/v1/operations")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "total_count" in data
        assert "active_count" in data
        assert isinstance(data["data"], list)

    @pytest.mark.api
    def test_list_operations_with_filters(self, client):
        """Test listing operations with status filter."""
        response = client.get("/api/v1/operations?status=completed&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    @pytest.mark.api
    def test_list_operations_active_only(self, client):
        """Test listing only active operations."""
        response = client.get("/api/v1/operations?active_only=true")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    @pytest.mark.api
    def test_get_operation_status_not_found(self, client):
        """Test getting status for non-existent operation.""" 
        response = client.get("/api/v1/operations/nonexistent_operation_id")

        assert response.status_code == 404

    @pytest.mark.api
    def test_cancel_operation_not_found(self, client):
        """Test cancelling non-existent operation."""
        response = client.delete("/api/v1/operations/nonexistent_operation_id")

        assert response.status_code == 404

    @pytest.mark.api
    def test_retry_operation_not_found(self, client):
        """Test retrying non-existent operation."""
        response = client.post("/api/v1/operations/nonexistent_operation_id/retry")

        assert response.status_code == 404

    @pytest.mark.api
    def test_list_operations_pagination(self, client):
        """Test operations list pagination parameters."""
        response = client.get("/api/v1/operations?limit=5&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) <= 5

    @pytest.mark.api
    def test_list_operations_by_type(self, client):
        """Test filtering operations by type."""
        response = client.get("/api/v1/operations?operation_type=data_load")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    @pytest.mark.api
    def test_cancel_operation_simple(self, client):
        """Test cancelling operation."""
        response = client.delete("/api/v1/operations/test_operation")

        # Should return 404 since operation doesn't exist
        assert response.status_code == 404

    @pytest.mark.api 
    def test_cancel_nonexistent_operation(self, client):
        """Test cancelling non-existent operation."""
        response = client.delete("/api/v1/operations/definitely_nonexistent_operation")

        # Should return 404 since operation doesn't exist
        assert response.status_code == 404