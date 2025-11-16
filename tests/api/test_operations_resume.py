"""
Unit tests for Operations Resume API endpoint.

Tests the POST /api/v1/operations/{operation_id}/resume endpoint
following TDD and async operations architecture.
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
    mock_instance.resume_operation = AsyncMock()
    return mock_instance


@pytest.fixture
def client_with_mocked_service(client, mock_operations_service):
    """Create a test client with mocked operations service."""
    from ktrdr.api.dependencies import get_operations_service

    # Override the dependency
    client.app.dependency_overrides[get_operations_service] = (
        lambda: mock_operations_service
    )

    yield client

    # Clean up
    client.app.dependency_overrides.clear()


class TestResumeOperationEndpoint:
    """Test resume operation API endpoint."""

    @pytest.mark.api
    def test_resume_operation_success(
        self, client_with_mocked_service, mock_operations_service
    ):
        """Test successfully resuming a failed operation."""
        # Mock successful resume
        mock_operations_service.resume_operation.return_value = {
            "success": True,
            "original_operation_id": "op_training_001",
            "new_operation_id": "op_training_new_001",
            "resumed_from_checkpoint": "epoch_snapshot",
            "message": "Operation resumed from epoch 45",
        }

        # Call endpoint
        response = client_with_mocked_service.post(
            "/api/v1/operations/op_training_001/resume"
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["original_operation_id"] == "op_training_001"
        assert data["new_operation_id"] == "op_training_new_001"
        assert data["resumed_from_checkpoint"] == "epoch_snapshot"
        assert "resumed from epoch 45" in data["message"]

        # Verify service was called
        mock_operations_service.resume_operation.assert_called_once_with(
            "op_training_001"
        )

    @pytest.mark.api
    def test_resume_operation_not_found(
        self, client_with_mocked_service, mock_operations_service
    ):
        """Test resume fails when operation doesn't exist."""
        # Mock operation not found
        mock_operations_service.resume_operation.side_effect = ValueError(
            "Operation not found: op_nonexistent"
        )

        # Call endpoint
        response = client_with_mocked_service.post(
            "/api/v1/operations/op_nonexistent/resume"
        )

        # Should return 404
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.api
    def test_resume_operation_wrong_status(
        self, client_with_mocked_service, mock_operations_service
    ):
        """Test resume fails for running operation."""
        # Mock wrong status error
        mock_operations_service.resume_operation.side_effect = ValueError(
            "Cannot resume running operation. Only FAILED or CANCELLED operations can be resumed."
        )

        # Call endpoint
        response = client_with_mocked_service.post(
            "/api/v1/operations/op_training_running/resume"
        )

        # Should return 400
        assert response.status_code == 400
        data = response.json()
        assert "cannot resume" in data["detail"].lower()

    @pytest.mark.api
    def test_resume_operation_no_checkpoint(
        self, client_with_mocked_service, mock_operations_service
    ):
        """Test resume fails when no checkpoint exists."""
        # Mock no checkpoint error
        mock_operations_service.resume_operation.side_effect = ValueError(
            "No checkpoint found for op_training_002. Cannot resume."
        )

        # Call endpoint
        response = client_with_mocked_service.post(
            "/api/v1/operations/op_training_002/resume"
        )

        # Should return 400
        assert response.status_code == 400
        data = response.json()
        assert "checkpoint" in data["detail"].lower()

    @pytest.mark.api
    def test_resume_cancelled_operation_success(
        self, client_with_mocked_service, mock_operations_service
    ):
        """Test successfully resuming a cancelled operation."""
        # Mock successful resume from cancelled
        mock_operations_service.resume_operation.return_value = {
            "success": True,
            "original_operation_id": "op_training_cancelled",
            "new_operation_id": "op_training_new_002",
            "resumed_from_checkpoint": "epoch_snapshot",
            "message": "Operation resumed from epoch 30",
        }

        # Call endpoint
        response = client_with_mocked_service.post(
            "/api/v1/operations/op_training_cancelled/resume"
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["original_operation_id"] == "op_training_cancelled"

    @pytest.mark.api
    def test_resume_backtesting_operation(
        self, client_with_mocked_service, mock_operations_service
    ):
        """Test resuming a backtesting operation."""
        # Mock successful backtest resume
        mock_operations_service.resume_operation.return_value = {
            "success": True,
            "original_operation_id": "op_backtest_001",
            "new_operation_id": "op_backtest_new_001",
            "resumed_from_checkpoint": "bar_snapshot",
            "message": "Operation resumed from bar 500",
        }

        # Call endpoint
        response = client_with_mocked_service.post(
            "/api/v1/operations/op_backtest_001/resume"
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["resumed_from_checkpoint"] == "bar_snapshot"
        assert "bar 500" in data["message"]

    @pytest.mark.api
    def test_resume_unsupported_operation_type(
        self, client_with_mocked_service, mock_operations_service
    ):
        """Test resume fails for unsupported operation types."""
        # Mock unsupported type error
        mock_operations_service.resume_operation.side_effect = ValueError(
            "Resume not supported for operation type: data_load"
        )

        # Call endpoint
        response = client_with_mocked_service.post(
            "/api/v1/operations/op_data_001/resume"
        )

        # Should return 400
        assert response.status_code == 400
        data = response.json()
        assert "not supported" in data["detail"].lower()

    @pytest.mark.api
    def test_resume_generic_error(
        self, client_with_mocked_service, mock_operations_service
    ):
        """Test resume handles generic errors properly."""
        # Mock generic exception
        mock_operations_service.resume_operation.side_effect = RuntimeError(
            "Database connection failed"
        )

        # Call endpoint
        response = client_with_mocked_service.post(
            "/api/v1/operations/op_training_003/resume"
        )

        # DataError returns 400 by default (client error from FastAPI's perspective)
        # Future enhancement: distinguish between client and server errors
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "OPERATIONS-ResumeError"
        assert "Failed to resume" in data["error"]["message"]
