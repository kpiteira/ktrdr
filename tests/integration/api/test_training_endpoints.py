"""
Integration tests for Training API endpoints.

Tests the training endpoints that start training operations and retrieve results
with properly mocked external dependencies.
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
def mock_training_service():
    """Create a mock TrainingService for testing endpoints."""
    service_mock = AsyncMock()

    # Mock successful start_training response
    service_mock.start_training.return_value = {
        "success": True,
        "task_id": "op_training_12345",
        "status": "training_started",
        "message": "Training started successfully",
        "symbols": ["AAPL"],
        "timeframes": ["1h"],
        "strategy_name": "rsi_mean_reversion",
        "estimated_duration_minutes": 30,
    }

    # Mock successful get_model_performance response
    service_mock.get_model_performance.return_value = {
        "success": True,
        "task_id": "completed_training_789",
        "status": "completed",
        "training_metrics": {
            "accuracy": 0.85,
            "loss": 0.15,
            "val_accuracy": 0.82,
            "val_loss": 0.18,
        },
        "test_metrics": {
            "accuracy": 0.80,
            "precision": 0.83,
            "recall": 0.78,
            "f1_score": 0.80,
        },
        "model_info": {
            "model_type": "mlp",
            "total_parameters": 1024,
            "training_time_seconds": 1800,
        },
    }

    return service_mock


@pytest.fixture
def client_with_mocked_training(client, mock_training_service):
    """Create a test client with mocked training service dependency."""
    from ktrdr.api.endpoints.training import get_training_service

    # Override the training service dependency
    client.app.dependency_overrides[get_training_service] = (
        lambda: mock_training_service
    )

    yield client

    # Clean up after test
    client.app.dependency_overrides.clear()


class TestTrainingEndpoints:
    """Test training API endpoints."""

    @pytest.mark.api
    def test_start_training_success(
        self, client_with_mocked_training, mock_training_service
    ):
        """Test starting a training operation successfully."""

        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
        }

        response = client_with_mocked_training.post(
            "/api/v1/trainings/start", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task_id"] == "op_training_12345"
        assert data["status"] == "training_started"
        assert data["symbols"] == ["AAPL"]
        assert data["timeframes"] == ["1h"]
        assert data["estimated_duration_minutes"] == 30

        # Verify the response structure matches expected format
        assert data["message"] == "Training started successfully"
        assert data["strategy_name"] == "rsi_mean_reversion"

        # Verify the service was called with correct parameters
        mock_training_service.start_training.assert_called_once_with(
            symbols=["AAPL"],
            timeframes=["1h"],
            strategy_name="rsi_mean_reversion",
            start_date="2024-01-01",
            end_date="2024-06-01",
            task_id=None,
            detailed_analytics=False,
        )

    @pytest.mark.api
    def test_start_training_with_optional_params(
        self, client_with_mocked_training, mock_training_service
    ):
        """Test starting training with optional parameters."""
        # Update mock response for this test
        mock_training_service.start_training.return_value["symbols"] = ["MSFT"]
        mock_training_service.start_training.return_value["timeframes"] = ["1d"]

        payload = {
            "symbols": ["MSFT"],
            "timeframes": ["1d"],
            "strategy_name": "rsi_mean_reversion",
            "task_id": "custom_task_id",
        }

        response = client_with_mocked_training.post(
            "/api/v1/trainings/start", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task_id"] == "op_training_12345"
        assert data["status"] == "training_started"
        assert data["symbols"] == ["MSFT"]
        assert data["timeframes"] == ["1d"]

        # Verify service call
        mock_training_service.start_training.assert_called_once_with(
            symbols=["MSFT"],
            timeframes=["1d"],
            strategy_name="rsi_mean_reversion",
            start_date=None,
            end_date=None,
            task_id="custom_task_id",
            detailed_analytics=False,
        )

    @pytest.mark.api
    def test_start_training_validation_error(self, client, mock_training_service):
        """Test starting training with invalid parameters - empty symbols list."""
        # Empty symbols list should fail validation (if provided, must be non-empty)
        payload = {
            "symbols": [],  # Empty list - should fail validation
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        assert response.status_code == 422  # Validation error

    @pytest.mark.api
    def test_start_training_service_error(
        self, client_with_mocked_training, mock_training_service
    ):
        """Test handling service errors during training start."""
        # Configure service to raise an exception
        from ktrdr.errors import DataError

        mock_training_service.start_training.side_effect = DataError(
            "Insufficient training data"
        )

        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
        }

        response = client_with_mocked_training.post(
            "/api/v1/trainings/start", json=payload
        )

        # DataError returns 503 (data unavailability)
        assert response.status_code == 503
        assert "Insufficient training data" in response.json()["detail"]

    @pytest.mark.api
    def test_get_model_performance_success(
        self, client_with_mocked_training, mock_training_service
    ):
        """Test getting model performance for completed training."""
        response = client_with_mocked_training.get(
            "/api/v1/trainings/completed_training_789/performance"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "training_metrics" in data
        assert "test_metrics" in data
        assert "model_info" in data

        # Verify service was called
        mock_training_service.get_model_performance.assert_called_once_with(
            "completed_training_789"
        )

    @pytest.mark.api
    def test_get_model_performance_not_completed(
        self, client_with_mocked_training, mock_training_service
    ):
        """Test getting performance for non-completed training."""
        from ktrdr.errors import DataError

        mock_training_service.get_model_performance.side_effect = DataError(
            "Training not completed"
        )

        response = client_with_mocked_training.get(
            "/api/v1/trainings/running_training/performance"
        )

        # DataError returns 503 (data unavailability)
        assert response.status_code == 503
        assert "Training not completed" in response.json()["detail"]

    @pytest.mark.api
    def test_training_config_validation(self, client, mock_training_service):
        """Test training configuration validation - empty symbol in list."""
        # Test with empty symbol in list (symbols are optional but if provided must be valid)
        payload = {
            "symbols": [""],  # Empty string in list should be invalid
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        # Should be caught by Pydantic validation
        assert response.status_code == 422

    @pytest.mark.api
    def test_training_config_defaults(
        self, client_with_mocked_training, mock_training_service
    ):
        """Test that training configuration uses proper defaults."""
        # Minimal payload - should use defaults for most config
        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
        }

        response = client_with_mocked_training.post(
            "/api/v1/trainings/start", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["strategy_name"] == "rsi_mean_reversion"
        assert data["timeframes"] == ["1h"]

    @pytest.mark.api
    def test_training_large_config(
        self, client_with_mocked_training, mock_training_service
    ):
        """Test training with large/complex configuration."""
        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1m"],
            "strategy_name": "rsi_mean_reversion",
            "start_date": "2020-01-01",  # Long training period
            "end_date": "2024-01-01",
        }

        response = client_with_mocked_training.post(
            "/api/v1/trainings/start", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.api
    def test_training_endpoints_error_handling(self, client, mock_training_service):
        """Test general error handling in training endpoints."""
        # Test non-existent training ID
        response = client.get("/api/v1/trainings/error_training")

        assert response.status_code == 404

    @pytest.mark.api
    def test_training_status_completed(self, client, mock_training_service):
        """Test getting status for completed training."""
        response = client.get("/api/v1/trainings/completed_training")

        # With real service, non-existent training returns 404
        assert response.status_code == 404

    @pytest.mark.api
    def test_training_with_custom_task_id(
        self, client_with_mocked_training, mock_training_service
    ):
        """Test starting training with custom task ID."""
        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
            "strategy_name": "rsi_mean_reversion",
            "task_id": "my_custom_training_id",
        }

        response = client_with_mocked_training.post(
            "/api/v1/trainings/start", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task_id"] == "op_training_12345"

    @pytest.mark.api
    def test_training_with_multiple_timeframes(
        self, client_with_mocked_training, mock_training_service
    ):
        """Test training with multiple timeframes."""
        # Update mock response for multiple timeframes
        mock_training_service.start_training.return_value["timeframes"] = ["1h", "1d"]

        payload = {
            "symbols": ["AAPL"],
            "timeframes": ["1h", "1d"],
            "strategy_name": "rsi_mean_reversion",
        }

        response = client_with_mocked_training.post(
            "/api/v1/trainings/start", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["timeframes"] == ["1h", "1d"]
        assert data["strategy_name"] == "rsi_mean_reversion"

    @pytest.mark.api
    def test_training_with_empty_timeframes(self, client, mock_training_service):
        """Test training with empty timeframes list."""
        payload = {
            "symbols": ["AAPL"],
            "timeframes": [],  # Empty list should be invalid
            "strategy_name": "rsi_mean_reversion",
        }

        response = client.post("/api/v1/trainings/start", json=payload)

        assert response.status_code == 422  # Validation error
