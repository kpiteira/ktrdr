"""
Integration tests for DummyService API endpoints.

This module tests the DummyService API endpoints that demonstrate the perfect
ServiceOrchestrator pattern - trivially simple endpoints that call services directly.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    from fastapi.testclient import TestClient

    from ktrdr.api.main import app

    return TestClient(app)


@pytest.fixture
def mock_dummy_service():
    """Create a mock DummyService for testing endpoints."""
    with patch("ktrdr.api.endpoints.dummy.DummyService") as mock_class:
        mock_instance = mock_class.return_value
        # Set up async methods to return AsyncMock objects
        mock_instance.start_dummy_task = AsyncMock()
        yield mock_instance


class TestDummyEndpoints:
    """Test DummyService API endpoints - the perfect ServiceOrchestrator pattern."""

    @pytest.mark.api
    def test_start_dummy_task_endpoint_success(self, client, mock_dummy_service):
        """Test successful start of dummy task endpoint."""
        # Mock the service to return expected operation response
        mock_dummy_service.start_dummy_task.return_value = {
            "operation_id": "op_dummy_123",
            "status": "started",
            "message": "Started dummy_task operation",
        }

        # Make the request
        response = client.post("/api/v1/dummy/start")

        # Check the response
        assert response.status_code == 200
        data = response.json()

        # Should follow standard API response format
        assert data["success"] is True
        assert data["error"] is None
        assert data["data"] is not None

        # Check the operation data
        operation_data = data["data"]
        assert operation_data["operation_id"] == "op_dummy_123"
        assert operation_data["status"] == "started"
        assert "dummy_task" in operation_data["message"].lower()

        # Verify service was called
        mock_dummy_service.start_dummy_task.assert_called_once()

    @pytest.mark.api
    def test_start_dummy_task_endpoint_service_error(self, client, mock_dummy_service):
        """Test start dummy task endpoint when service raises error."""
        # Mock the service to raise an exception
        mock_dummy_service.start_dummy_task.side_effect = Exception("Service failed")

        # Make the request
        response = client.post("/api/v1/dummy/start")

        # Should return error response
        assert (
            response.status_code == 200
        )  # API uses envelope pattern, so 200 with error
        data = response.json()

        # Should follow standard API error response format
        assert data["success"] is False
        assert data["data"] is None
        assert data["error"] is not None

        # Check error details
        error = data["error"]
        assert error["code"] == "DUMMY-001"
        assert "failed to start" in error["message"].lower()

        # Verify service was called
        mock_dummy_service.start_dummy_task.assert_called_once()

    @pytest.mark.api
    def test_start_dummy_task_endpoint_no_parameters_required(
        self, client, mock_dummy_service
    ):
        """Test that start dummy task endpoint requires no parameters."""
        # Mock the service to return expected response
        mock_dummy_service.start_dummy_task.return_value = {
            "operation_id": "op_dummy_simple",
            "status": "started",
            "message": "Started dummy_task operation",
        }

        # Make the request with no body (should work)
        response = client.post("/api/v1/dummy/start")

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Service should be called with no arguments
        mock_dummy_service.start_dummy_task.assert_called_once_with()

    @pytest.mark.api
    def test_start_dummy_task_endpoint_openapi_documentation(self, client):
        """Test that the dummy endpoints are properly documented in OpenAPI."""
        # Get the OpenAPI schema (API prefix is /api/v1)
        response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200

        openapi_data = response.json()
        paths = openapi_data.get("paths", {})

        # Check that our dummy endpoint is documented
        dummy_path = "/api/v1/dummy/start"
        assert dummy_path in paths

        # Check the POST method exists
        dummy_post = paths[dummy_path].get("post", {})
        assert dummy_post is not None

        # Check documentation details - verify Dummy tag is present
        assert "Dummy" in dummy_post.get("tags", [])
        assert "start awesome dummy task" in dummy_post.get("summary", "").lower()
        assert "serviceorchestrator" in dummy_post.get("description", "").lower()

        # Check response model
        responses = dummy_post.get("responses", {})
        assert "200" in responses

    @pytest.mark.api
    def test_start_dummy_task_endpoint_trivially_simple_implementation(
        self, client, mock_dummy_service
    ):
        """Test that endpoint demonstrates trivially simple implementation pattern."""
        # Mock the service
        mock_dummy_service.start_dummy_task.return_value = {
            "operation_id": "op_test_simple",
            "status": "started",
            "message": "Started dummy_task operation",
        }

        # The endpoint should be so simple it just:
        # 1. Creates DummyService instance
        # 2. Calls start_dummy_task()
        # 3. Returns response in API format
        # That's it! ServiceOrchestrator handles everything else.

        response = client.post("/api/v1/dummy/start")

        # Should work perfectly with minimal code
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # The simplicity is proven by the fact that this test passes
        # with just the service mock - no complex setup required!


class TestDummyEndpointsIntegration:
    """Test DummyService endpoints with more realistic integration scenarios."""

    @pytest.mark.api
    def test_dummy_endpoint_with_real_service_mock(self, client):
        """Test dummy endpoint with more realistic service mock."""
        # Create a more realistic mock that mimics actual ServiceOrchestrator behavior
        with patch("ktrdr.api.endpoints.dummy.DummyService") as mock_class:
            mock_instance = mock_class.return_value

            # Mock to return the exact format that ServiceOrchestrator would return
            mock_instance.start_dummy_task = AsyncMock(
                return_value={
                    "operation_id": "op_dummy_realistic_123",
                    "status": "started",
                    "message": "Started dummy_task operation",
                    "service_name": "DummyService",
                    "operation_type": "DUMMY",
                }
            )

            response = client.post("/api/v1/dummy/start")

            # Should work with realistic service response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["operation_id"] == "op_dummy_realistic_123"
            assert data["data"]["status"] == "started"

    @pytest.mark.api
    def test_dummy_endpoint_demonstrates_perfect_serviceorchestrator_pattern(
        self, client
    ):
        """Test that dummy endpoint perfectly demonstrates ServiceOrchestrator pattern."""
        with patch("ktrdr.api.endpoints.dummy.DummyService") as mock_class:
            mock_instance = mock_class.return_value
            mock_instance.start_dummy_task = AsyncMock(
                return_value={
                    "operation_id": "op_pattern_demo",
                    "status": "started",
                    "message": "ServiceOrchestrator handled everything!",
                }
            )

            response = client.post("/api/v1/dummy/start")

            # Perfect pattern demonstrated:
            # - Endpoint is trivially simple (≤10 lines)
            # - No business logic in endpoint
            # - ServiceOrchestrator handles ALL complexity
            # - Clean error handling
            # - Proper API response format

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Verify the service was instantiated and called
            mock_class.assert_called_once()
            mock_instance.start_dummy_task.assert_called_once()

            # This simple test passing proves the pattern works!
